"""Nomad - Stage 9: score NOMAD on the golden set (eval/golden_set.csv, 16 questions, every answer checked word for
word in its official text).

A. Rules: for each question, the value NOMAD's code uses and the article it cites. The value is read from the code
   file named below (the check fails if that literal is not in the file), so the score follows the code.
   answer correct  = NOMAD's value equals the golden answer (for G02, "not checked" is right: the rule is not in force)
   citation correct = NOMAD's citation names the golden article number
   coverage        = questions NOMAD checks at all
B. Search (Stage 2 baseline): BM25 keyword search over the 2,470 rulebook pieces with each question's Catalan query;
   hit@k = the golden piece is in the top k. MRR = mean of 1 / rank.
Run:  .venv/Scripts/python src/eval/run_golden.py
Out:  results/eval/golden_scores.csv + golden_summary.json
"""
import csv, json, math, re, unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "eval"

# qid -> (value NOMAD uses or None if not checked, code file, literal that must be in that file, NOMAD's citation)
NOMAD = {
    "G01": (36.0, "src/sim/unit_mix.py", '"min_useful_cat": (36.0', "Decret 141/2012, Annex 1, 3.1"),
    "G02": (None, "", "", ""),
    "G03": (2.8, "src/generate/layout.py", "min(r[\"w\"], r[\"d\"]) >= 2.8", "Decret 141/2012 Annex 1 3.7.2"),
    "G04": (6.0, "src/generate/layout.py", 'r["area"] >= 6.0', "Decret 141/2012 Annex 1 3.8"),
    "G05": (2.0, "src/generate/layout.py", "else 2.0", "Decret 141/2012 Annex 1 3.8"),
    "G06": (2.2, "src/generate/layout.py", 'r["w"] >= 2.2', "Decret 141/2012 Annex 1 3.7.2"),
    "G07": (2.5, "src/sim/unit_mix.py", '"min_height": (2.50', "Decret 141/2012, Annex 1, 3.5"),
    "G08": (2.2, "src/generate/layout.py", "height >= 2.2", "Decret 141/2012 Annex 1 3.5"),
    "G09": (0.125, "src/generate/layout.py", "ratio >= 1.0 / 8.0", "Decret 141/2012 Annex 1 3.9.1"),
    "G10": (1.0, "src/generate/layout.py", 'min(r["w"], r["d"]) >= 1.0', "Decret 141/2012 Annex 1 3.4.1.d"),
    "G11": (40.0, "src/generate/layout.py", "S >= 40.0", "MPGM 2004 Barcelona DA1 2.a"),
    "G12": (3.0, "src/check/flags.py", "fac_len >= 3.0", "MPGM 2004 Barcelona DA1 2.b"),
    "G13": (80.0, "src/sim/unit_mix.py", '"density_module": (80.0', "MPGM 2004 Barcelona art. 318 (zone 12) / art. 323"),
    "G14": (2.4, "src/check/flags.py", "MIN_HEIGHT = 2.40", "Decret 141/2012 Annex 4 apartat 2 (group C)"),
    "G15": (3.0, "src/generate/better.py", "3 m circle", "Decret 141/2012 Annex 1 2.5.1"),
    "G16": (1.0 / 9.0, "src/generate/layout.py", "S / 9.0", "Decret 141/2012 Annex 1 3.6.2"),
}


def art_no(s):
    """The article / section number in a citation, e.g. '3.7.2', 'DA1 2.a' -> '2.a', 'art. 323' -> '323'."""
    m = re.findall(r"(\d+(?:\.\d+)*(?:\.[a-z])?)", s.replace("Disposició addicional", "DA").replace("DA1", "DA"))
    m = [x for x in m if x not in ("141", "2012", "2004", "1")]
    return m[-1] if m else ""


def norm_text(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def tokens(s):
    return [t for t in re.findall(r"[a-z0-9]+(?:[.,/][0-9]+)?", norm_text(s)) if len(t) > 1]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [tokens(d) for d in docs]
        self.n = len(self.docs)
        self.avg = sum(map(len, self.docs)) / self.n
        self.df = Counter(t for d in self.docs for t in set(d))
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def search(self, q, k=10):
        qt = tokens(q)
        sc = []
        for i, (tf, d) in enumerate(zip(self.tf, self.docs)):
            s = 0.0
            for t in qt:
                if t in tf:
                    idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            sc.append((s, i))
        return [i for s, i in sorted(sc, reverse=True)[:k] if s > 0]


def main():
    gold = list(csv.DictReader(open(ROOT / "eval" / "golden_set.csv", encoding="utf-8")))
    chunks = [json.loads(l) for l in open(ROOT / "data" / "rulebook.jsonl", encoding="utf-8")]
    bm = BM25([(c.get("title") or "") + " " + c["text"] for c in chunks])
    rows = []
    for g in gold:
        val, path, literal, cite = NOMAD[g["qid"]]
        in_code = (literal in (ROOT / path).read_text(encoding="utf-8")) if path else None
        checked = val is not None
        if g["correct_answer"] == "not in force":
            ans_ok = not checked
        else:
            ans_ok = checked and in_code and abs(val - float(g["correct_answer"])) < 1e-3
        cite_ok = (art_no(cite) == art_no(g["source_article"])) if checked else None
        nm = "Decret 141/2012" if "Decret" in g["source_article"] else "MPGM 2004"
        hits = bm.search(g["query"], 10)
        rank = next((r + 1 for r, i in enumerate(hits) if chunks[i]["block_id"] == g["source_block_id"] and nm in chunks[i]["norm"]), None)
        rows.append({"qid": g["qid"], "question": g["question"], "golden": g["correct_answer"], "nomad": "not checked" if not checked else round(val, 4),
                     "code_has_value": in_code, "answer_ok": ans_ok, "nomad_cite": cite, "cite_ok": cite_ok,
                     "search_rank": rank, "top1": "%s | %s" % (chunks[hits[0]]["norm"], chunks[hits[0]]["block_id"]) if hits else ""})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "golden_scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    checked = [r for r in rows if r["nomad"] != "not checked"]
    n = len(rows)
    summ = {"questions": n,
            "answer_accuracy": round(sum(r["answer_ok"] for r in rows) / n, 3),
            "coverage": round(len(checked) / n, 3),
            "answer_accuracy_when_checked": round(sum(r["answer_ok"] for r in checked) / len(checked), 3),
            "citation_accuracy_when_checked": round(sum(bool(r["cite_ok"]) for r in checked) / len(checked), 3),
            "search_hit@1": round(sum(1 for r in rows if r["search_rank"] == 1) / n, 3),
            "search_hit@5": round(sum(1 for r in rows if r["search_rank"] and r["search_rank"] <= 5) / n, 3),
            "search_hit@10": round(sum(1 for r in rows if r["search_rank"]) / n, 3),
            "search_mrr": round(sum(1.0 / r["search_rank"] for r in rows if r["search_rank"]) / n, 3),
            "wrong": [r["qid"] for r in rows if not r["answer_ok"]],
            "not_checked": [r["qid"] for r in rows if r["nomad"] == "not checked"]}
    json.dump(summ, open(OUT / "golden_summary.json", "w"), indent=1)
    for r in rows:
        print("%s answer %-5s cite %-5s rank %-4s golden %-12s nomad %s" % (r["qid"], r["answer_ok"], r["cite_ok"], r["search_rank"], r["golden"], r["nomad"]))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
