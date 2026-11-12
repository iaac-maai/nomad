"""Nomad - Step 1 final: merge every source file into ONE rulebook.

Each collect script writes its own file (data/<level>/<source>_chunks.jsonl). This script:
1. reads all of them, level by level (national -> catalonia -> pgm -> barcelona),
2. splits very long pieces into parts of ~4000 characters (cut at paragraph lines, never mid-row of a table),
3. marks pieces whose formulas are drawn in 2D on the page ("note": "check_pdf ..."), so nobody trusts the text blindly,
4. writes data/<level>/chunks.jsonl, 4_laws_and_rules/output/rulebook.jsonl (everything) and 4_laws_and_rules/output/rulebook_summary.csv.
"""
import glob, json, os, re
import pandas as pd

LEVELS = ["national", "catalonia", "pgm", "barcelona"]
MAX_CHARS = 4000


def split_long(c):
    """Cut a long piece into parts at line breaks. Tables cut in two get a '[Tabla cont.]' marker."""
    if len(c["text"]) <= MAX_CHARS:
        return [c]
    parts, cur, size, in_table = [], [], 0, False
    lines = []
    for line in c["text"].split("\n"):   # a paragraph longer than a part is cut at sentence ends
        lines += re.split(r"(?<=[.;:])\s+(?=[A-ZÀ-Ú0-9(])", line) if len(line) > MAX_CHARS else [line]
    for line in lines:
        if size + len(line) > MAX_CHARS and cur:
            if in_table:
                cur.append("[/Tabla]")
            parts.append("\n".join(cur))
            cur, size = (["[Tabla cont.]"] if in_table else []), 0
        cur.append(line)
        size += len(line) + 1
        if line.startswith("[Tabla"):
            in_table = True
        elif line == "[/Tabla]":
            in_table = False
    parts.append("\n".join(cur))
    out = []
    for i, text in enumerate(parts, 1):
        p = dict(c)
        p["block_id"] = f"{c['block_id']}/p{i}"
        p["title"] = f"{c['title'] or c['block_type']} (parte {i}/{len(parts)})"
        p["text"] = text if i == 1 else f"[{c['title'] or c['block_type']}, continuación]\n{text}"
        p["part"] = f"{i}/{len(parts)}"
        out.append(p)
    return out


def formula_fragments(text):
    """Count tiny lines (1-3 characters) outside tables. A formula drawn in 2D on the page
    (fractions, sub/superscripts) is read as many such fragments: 'fi', 'd', '2,0', ..."""
    n, in_table = 0, False
    for line in text.split("\n"):
        if line.startswith("[Tabla"):
            in_table = True
        elif line == "[/Tabla]":
            in_table = False
        elif not in_table and len(line.replace(" ", "")) <= 3:
            n += 1
    return n


def main():
    everything, rows = [], []
    for level in LEVELS:
        chunks = []
        for path in sorted(glob.glob(f"data/{level}/*_chunks.jsonl")):
            with open(path, encoding="utf-8") as f:
                chunks += [json.loads(l) for l in f]
        out = []
        for c in chunks:
            c.setdefault("level", level)
            for p in split_long(c):
                if p.get("note"):   # the source already wrote a note (e.g. "official guidance")
                    out.append(p)
                    continue
                if formula_fragments(p["text"]) >= 5:
                    p["note"] = "check_pdf: contains formulas drawn on the page; read the PDF page before using numbers"
                out.append(p)
        if not out:
            continue
        with open(f"data/{level}/chunks.jsonl", "w", encoding="utf-8") as f:
            for c in out:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        everything += out
        df = pd.DataFrame(out)
        for norm, g in df.groupby("norm", sort=False):
            rows.append({"level": level, "norm": norm, "pieces": len(g),
                         "split_parts": int(g.get("part", pd.Series(dtype=str)).notna().sum()) if "part" in g else 0,
                         "check_pdf": int(g["note"].notna().sum()) if "note" in g else 0,
                         "longest": int(g["text"].str.len().max())})

    ids = [(c["norm"], c["block_id"]) for c in everything]
    assert len(ids) == len(set(ids)), "duplicate block ids"
    with open("4_laws_and_rules/output/rulebook.jsonl", "w", encoding="utf-8") as f:
        for c in everything:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    s = pd.DataFrame(rows)
    s.to_csv("4_laws_and_rules/output/rulebook_summary.csv", index=False)
    print(s.to_string(index=False))
    print("Rulebook pieces:", len(everything))


if __name__ == "__main__":
    main()
