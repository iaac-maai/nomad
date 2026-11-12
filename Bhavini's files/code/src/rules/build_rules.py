"""Nomad - Stage 3: the rule cards NOMAD checks, as machine-readable JSON (rules/rules.json), each tied to its
official text in the rulebook (data/rulebook.jsonl).

Each card: rule_id, level, applies_to, parameter, operator, value, unit, source {norm, article, block_id, url},
quote (the sentence of the official text, copied from the rulebook chunk), used_by (where NOMAD applies it).
Automatic self-checks (CLAUDE.md, Stage 3):
  1. schema valid (pydantic)
  2a. the quote appears word for word in its rulebook chunk
  2b. the value appears in the quote (written the way the law writes it, e.g. "2,80 m", "1/8")
These cards were written by hand from the official text, not by an LLM, so the 5-run agreement test does not
apply here (the team's Exp 2 tests the LLM). confidence = share of automatic checks passed; a card below 1.0
goes to rules/review.json for a person to check against the PDF.

Run:  .venv/Scripts/python src/rules/build_rules.py
"""
import json, re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
RULEBOOK = ROOT / "data" / "rulebook.jsonl"

# (rule_id, level, applies_to, parameter, operator, value, unit, norm, block_id, quote anchor (regex), value as written,
#  used_by, note)
SPEC = [
    ("CAT-141-2012-area-01", "catalonia", "dwelling", "useful_area", ">=", 36.0, "m2", "Decret 141/2012", "annex1-3.1",
     r"36\s*m", "36", "src/generate/layout.py CITE useful; src/sim/unit_mix.py min_useful_cat", ""),
    ("BCN-MPGM2004-area-01", "barcelona", "dwelling", "useful_area", ">=", 40.0, "m2", "MPGM 2004",
     "MPGM-2004-habitatges-parcela:disposicions-addicionals-de-la-m", r"mínima de 40", "40",
     "src/generate/layout.py CITE useful; src/sim/unit_mix.py min_useful_bcn", "Barcelona raises the Catalan 36 m² to 40 m²."),
    ("BCN-MPGM2004-facade-01", "barcelona", "dwelling", "facade_contact_length", ">=", 3.0, "m", "MPGM 2004",
     "MPGM-2004-habitatges-parcela:disposicions-addicionals-de-la-m", r"longitud de 3 m", "3 m",
     "src/check/flags.py cards facade; src/sim/unit_mix.py min_facade_bcn", ""),
    ("CAT-141-2012-facade-01", "catalonia", "dwelling", "facade_length / useful_area", ">=", 1.0 / 9.0, "m per m2",
     "Decret 141/2012", "annex1-3.6", r"S\s*/\s*9", "S/9", "src/generate/layout.py CITE facade; src/sim/unit_mix.py facade_ratio", ""),
    ("CAT-141-2012-height-01", "catalonia", "room", "clear_height", ">=", 2.50, "m", "Decret 141/2012", "annex1-3.5",
     r"2,50\s*m", "2,50", "src/check/flags.py cards height; src/generate/layout.py CITE height", ""),
    ("CAT-141-2012-height-04C", "catalonia", "room (change of use)", "clear_height", ">=", 2.40, "m", "Decret 141/2012",
     "annex4-apartat-2", r"2,40\s*m", "2,40", "not used yet",
     "Team finding (Exp 2): a shop conversion falls under Annex 4 group C, so 2,40 m applies instead of 2,50 m."),
    ("CAT-141-2012-bedroom-01", "catalonia", "bedroom", "useful_area", ">=", 6.0, "m2", "Decret 141/2012", "annex1-3.8",
     r"6\s*m", "6 m", "src/generate/layout.py CITE bedroom; src/sim/unit_mix.py min_bedroom", ""),
    ("CAT-141-2012-bedroom-02", "catalonia", "bedroom", "inscribed_square_side", ">=", 2.00, "m", "Decret 141/2012",
     "annex1-3.8", r"2,00\s*m", "2,00", "src/generate/layout.py CITE bedroom",
     "Conditional: one bedroom needs 2,60 m when the dwelling has 3 or more bedrooms (same article)."),
    ("CAT-141-2012-living-01", "catalonia", "living room", "inscribed_circle_diameter", ">=", 2.80, "m", "Decret 141/2012",
     "annex1-3.7.2", r"2,80\s*m", "2,80", "src/generate/layout.py CITE living", ""),
    ("CAT-141-2012-window-01", "catalonia", "room", "window_area / floor_area", ">=", 1.0 / 8.0, "ratio", "Decret 141/2012",
     "annex1-3.9", r"1/8", "1/8", "src/generate/layout.py CITE windows; src/sim/unit_mix.py window_ratio", ""),
    ("CAT-141-2012-bath-01", "catalonia", "dwelling", "toilets (0-3 bedrooms)", ">=", 1.0, "count", "Decret 141/2012",
     "annex1-3.11", r"Vàter \| 1", "1", "src/generate/layout.py CITE bath", "2 toilets from 4 bedrooms (same table)."),
    ("CAT-141-2012-patio-01", "catalonia", "patio that lights rooms", "area", ">=", 9.0, "m2", "Decret 141/2012",
     "annex1-2.5.1", r"9\s*m", "9", "src/generate/better.py CITE patio", ""),
    ("CTE-SUA-corridor-01", "national", "shared corridor (accessible route)", "clear_width", ">=", 1.20, "m", "CTE-DB-SUA",
     "AnejoA/p1", r"Anchura libre de paso\s*≥\s*1,20", "1,20", "src/generate/better.py CITE corridor",
     "The table row was garbled when the PDF was read; the same table admits 1,10 m in shared areas of housing."),
    ("CTE-SUA-door-01", "national", "door on an accessible route", "clear_width", ">=", 0.80, "m", "CTE-DB-SUA",
     "AnejoA/p1", r"Anchura libre de paso ≥ 0,80 m", "0,80", "src/rhino/nomad_model.py DOOR_W (Stage 7.2)", ""),
    ("BCN-MPGM2004-density-12", "pgm", "building in zone 12 (casc antic)", "dwellings <= built_area / module", "<=", 80.0,
     "m2 per dwelling", "MPGM 2004", "MPGM-2004-habitatges-parcela:art.-318.", r"mòdul de 80 m", "80",
     "src/check/flags.py cards density; src/sim/unit_mix.py density_module", "Rounded up ('per excés')."),
    ("BCN-MPGM2004-density-13", "pgm", "building in zone 13 (densificació urbana, e.g. Eixample)",
     "dwellings <= built_area / module", "<=", 80.0, "m2 per dwelling", "MPGM 2004", "MPGM-2004-habitatges-parcela:art.-323.",
     r"mòdul de 80 m", "80", "src/check/flags.py cards density; src/sim/unit_mix.py density_module",
     "Same module as zone 12; the Ajuntament's 2025 guide applies it to every change of use (section 'tercer')."),
]


class Source(BaseModel):
    norm: str
    article: Optional[str]
    block_id: str
    url: str


class Card(BaseModel):
    rule_id: str
    level: str
    applies_to: str
    parameter: str
    operator: str
    value: float
    unit: str
    source: Source
    quote: str
    used_by: str
    note: str
    checks: dict
    confidence: float


def sentence(text, m):
    """The sentence of text around match m (split at '. ' or line ends; tables kept as a row)."""
    starts = [0] + [x.end() for x in re.finditer(r"(?<=[.;:\]])\s+(?=[A-ZÀ-Ú0-9\[])", text)
                    if not re.search(r"\b(art|núm|apt)\.$", text[:x.start()], re.I)]          # not after "art."
    a = max(s for s in starts if s <= m.start())
    nxt = re.search(r"[.;](\s|$)", text[m.end():])
    b = m.end() + (nxt.end() if nxt else len(text) - m.end())
    return text[a:b].strip()


def main():
    chunks = [json.loads(l) for l in open(RULEBOOK, encoding="utf-8")]
    cards, review = [], []
    for (rid, level, applies, param, op, value, unit, norm, block, anchor, written, used, note) in SPEC:
        ch = [c for c in chunks if norm in c["norm"] and c["block_id"] == block]
        c = ch[0] if ch else None
        m = re.search(anchor, c["text"]) if c else None
        quote = sentence(c["text"], m) if m else ""
        checks = {"source_found": c is not None, "quote_in_source": bool(quote) and quote in (c["text"] if c else ""),
                  "value_in_quote": bool(quote) and written in quote}
        card = Card(rule_id=rid, level=level, applies_to=applies, parameter=param, operator=op, value=round(value, 4),
                    unit=unit, source=Source(norm=c["norm"] if c else norm, article=c.get("title") if c else None,
                                             block_id=block, url=c["source_url"] if c else ""),
                    quote=quote, used_by=used, note=note, checks=checks,
                    confidence=round(sum(checks.values()) / len(checks), 2))
        cards.append(card.model_dump())
        if card.confidence < 1.0:
            review.append({"rule_id": rid, "why": [k for k, v in checks.items() if not v], "note": note})
    (ROOT / "rules").mkdir(exist_ok=True)
    json.dump(cards, open(ROOT / "rules" / "rules.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(review, open(ROOT / "rules" / "review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for c in cards if c["confidence"] == 1.0)
    print("%d rule cards, %d pass every automatic check, %d to review" % (len(cards), ok, len(review)))
    for c in cards:
        print("%-26s %-5s %s" % (c["rule_id"], "OK" if c["confidence"] == 1 else "CHECK", c["quote"][:150].replace("\n", " ")))


if __name__ == "__main__":
    main()
