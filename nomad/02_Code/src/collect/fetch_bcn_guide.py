"""Nomad - Step 1e (part): Ajuntament de Barcelona guide for changing a local into housing
(March 2025). It is official guidance, not a norm, but it names every rule the city checks.
We keep the Catalan version and cut it at PRIMER / SEGON / TERCER / QUART / CINQUÈ / OBSERVACIONS."""
import json, os, re
import requests
import pymupdf

URL = ("https://ajuntament.barcelona.cat/urbanisme-accio-climatica-mobilitat-pla-barris-serveis-urbans/"
       "sites/default/files/2025-03/InforUrb_Canvi-us-habitatge.pdf")
RAW = "data/barcelona/raw/InforUrb_Canvi-us-habitatge.pdf"
OUT = "data/barcelona/bcn_guide_chunks.jsonl"
STEPS = ["PRIMER", "SEGON", "TERCER", "QUART", "CINQUÈ", "OBSERVACIONS"]


def main():
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    if not os.path.exists(RAW):
        r = requests.get(URL, timeout=60)
        r.raise_for_status()
        with open(RAW, "wb") as f:
            f.write(r.content)
    doc = pymupdf.open(RAW)
    pages = [(i + 1, p.get_text()) for i, p in enumerate(doc)]
    chunks, cur = [], None
    for page_no, text in pages:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("Català") or line.startswith("Urbanisme –") or line == "Informació i Documentació":
                continue
            if "[Fi de la versió catalana]" in line:
                break
            step = next((s for s in STEPS if re.match(rf"^{s}\b", line)), None)
            if step:
                cur = {"step": step, "page": page_no, "lines": []}
                chunks.append(cur)
            if cur:
                cur["lines"].append(line)
        else:
            continue
        break   # stop after the Catalan version

    out = []
    for c in chunks:
        out.append({
            "norm_id": "BCN-InforUrb-canvi-us-2025", "norm": "BCN Guia canvi d'ús local→habitatge",
            "level": "barcelona", "block_id": c["step"].lower(), "block_type": "guia",
            "title": f"{c['step'].capitalize()} - canvi d'ús de locals a habitatge",
            "in_force_from": None,
            "source_url": f"{URL}#page={c['page']}",
            "text": re.sub(r"(\w)-\n(\w)", r"\1\2", "\n".join(c["lines"])),
            "note": "official guidance (Ajuntament de Barcelona, 2025-03), not a norm: cite the norms it names",
        })
    with open(OUT, "w", encoding="utf-8") as f:
        for c in out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(len(out), "chunks:", [c["block_id"] for c in out])


if __name__ == "__main__":
    main()
