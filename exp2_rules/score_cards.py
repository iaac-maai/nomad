"""Experiment 2, step 2: how good and how sure is the AI?

Reads outputs/drafts.jsonl (AI cards) and exp2_rules/gold_cards.csv (your hand-made correct cards).
For every draft it checks:
  - quote_found:      is the quote really in the PDF? (word for word, accents ignored)
  - number_in_quote:  is the value really written inside that quote?
  - agreement:        how many of the 5 runs gave the same card?
  - correct:          does it match the gold card?
Then a small logistic-regression "trust layer" learns to predict "correct" from the first three
signals, tested question by question (leave-one-question-out).

Run from the repo root:
    python exp2_rules/score_cards.py
Results: outputs/exp2_per_draft.csv, outputs/exp2_per_question.csv, outputs/exp2_summary.md
"""
import csv
import json
import re
from collections import Counter

from common import OUT, ROOT, light, load_env, load_pdf_pages, norm, pdf_path

APPROVE_AT = 0.8  # confidence needed to skip the expert


def to_float(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def number_variants(v, unit):
    out = set()
    for fmt in ("%g", "%.1f", "%.2f"):
        s = fmt % v
        out.update({s, s.replace(".", ",")})
    if unit == "ratio" or 0 < v < 1:
        pct = v * 100
        for fmt in ("%g", "%.1f"):
            s = fmt % pct
            out.update({s, s.replace(".", ",")})
        if v > 0:
            n = 1 / v
            if abs(n - round(n)) < 0.02:
                out.add("1/%d" % round(n))
    return out


def number_in_quote(value, unit, quote):
    if value is None or not quote:
        return False
    q = light(quote)
    for s in number_variants(value, unit):
        if re.search(r"(?<![\d.,/])" + re.escape(s) + r"(?![\d/])", q):
            return True
    return False


def find_quote(quote, pages_norm, pages_words):
    """Return (found, page, coverage). coverage = share of quote words seen on the best page."""
    qn = norm(quote)
    if not qn:
        return False, None, 0.0
    for i, p in enumerate(pages_norm):
        if qn in p:
            return True, i + 1, 1.0
    words = [w for w in qn.split() if len(w) >= 3]
    if not words:
        return False, None, 0.0
    best_page, best = None, 0.0
    for i, ws in enumerate(pages_words):
        cov = sum(1 for w in words if w in ws) / len(words)
        if cov > best:
            best_page, best = i + 1, cov
    return False, best_page, round(best, 3)


def same_card(a, b):
    """Two cards agree if the check type is the same and the values are within 1 %."""
    if a is None or b is None or a.get("check") != b.get("check"):
        return False
    va, vb = to_float(a.get("value")), to_float(b.get("value"))
    if va is None or vb is None:
        return va is None and vb is None
    return abs(va - vb) <= max(0.005, 0.01 * abs(vb))


def main():
    load_env()
    pages = load_pdf_pages(pdf_path())
    pages_norm = [norm(p) for p in pages]
    pages_words = [set(p.split()) for p in pages_norm]

    # last successful record per (question, run)
    drafts = {}
    with open(OUT / "drafts.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("card") is not None:
                drafts[(rec["id"], rec["run"])] = rec
    if not drafts:
        raise SystemExit("No drafts yet. Run python exp2_rules/draft_cards.py first.")

    gold = {}
    with open(ROOT / "exp2_rules" / "gold_cards.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if to_float(row.get("value")) is not None:
                row["value"] = to_float(row["value"])
                gold[row["id"]] = row
    missing = sorted({qid for qid, _ in drafts} - set(gold))
    if missing:
        print("Gold card missing for: %s (accuracy skipped for these)" % ", ".join(missing))

    by_q = {}
    for (qid, run), rec in sorted(drafts.items()):
        by_q.setdefault(qid, []).append(rec)

    rows = []
    for qid, recs in by_q.items():
        cards = [r["card"] for r in recs]
        for rec in recs:
            c = rec["card"]
            val = to_float(c.get("value"))
            found, page, cov = find_quote(c.get("quote", ""), pages_norm, pages_words)
            agree = sum(1 for other in cards if same_card(c, other)) / len(cards)
            g = gold.get(qid)
            rows.append({
                "id": qid, "run": rec["run"], "check": c.get("check"), "value": val,
                "unit": c.get("unit"), "quote_found": int(found), "quote_page": page,
                "quote_coverage": cov,
                "number_in_quote": int(number_in_quote(val, c.get("unit"), c.get("quote", ""))),
                "agreement": round(agree, 2),
                "correct": "" if g is None else int(same_card(c, g)),
                "quote": c.get("quote", ""),
            })

    # ---- per question
    qrows = []
    for qid, recs in by_q.items():
        rs = [r for r in rows if r["id"] == qid]
        top = Counter((r["check"], None if r["value"] is None else round(r["value"], 3)) for r in rs).most_common(1)[0]
        grounding = sum(r["quote_found"] and r["number_in_quote"] for r in rs) / len(rs)
        agreement = top[1] / len(rs)
        conf = round(agreement * grounding, 2)
        g = gold.get(qid)
        acc = "" if g is None else round(sum(r["correct"] for r in rs) / len(rs), 2)
        maj_ok = "" if g is None else int(same_card({"check": top[0][0], "value": top[0][1]}, g))
        qrows.append({"id": qid, "runs": len(rs), "majority_check": top[0][0], "majority_value": top[0][1],
                      "gold_value": "" if g is None else g["value"], "agreement": round(agreement, 2),
                      "grounding": round(grounding, 2), "accuracy": acc, "majority_correct": maj_ok,
                      "confidence": conf, "decision": "auto-approve" if conf >= APPROVE_AT else "expert check"})

    # ---- small ML trust layer: logistic regression, leave-one-question-out
    ml_text = "Not enough labelled data yet (need gold cards for 3+ questions and both right and wrong drafts)."
    labelled = [r for r in rows if r["correct"] != ""]
    if len({r["id"] for r in labelled}) >= 3 and len({r["correct"] for r in labelled}) == 2:
        try:
            import numpy as np
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import LeaveOneGroupOut
            X = np.array([[r["quote_found"], r["number_in_quote"], r["quote_coverage"], r["agreement"]] for r in labelled])
            y = np.array([r["correct"] for r in labelled])
            groups = np.array([r["id"] for r in labelled])
            prob = np.zeros(len(y))
            for tr, te in LeaveOneGroupOut().split(X, y, groups):
                if len(set(y[tr])) < 2:
                    prob[te] = y[tr].mean()
                    continue
                prob[te] = LogisticRegression().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
            acc_ml = float(((prob >= 0.5) == y).mean())
            acc_base = float(max(y.mean(), 1 - y.mean()))
            brier = float(((prob - y) ** 2).mean())
            for r, p in zip(labelled, prob):
                r["p_correct"] = round(float(p), 2)
            ml_text = ("Logistic regression on 4 signals, leave-one-question-out: accuracy %.2f "
                       "(always-guess baseline %.2f), Brier score %.3f, %d drafts."
                       % (acc_ml, acc_base, brier, len(y)))
        except ImportError:
            ml_text = "scikit-learn not installed: pip install -r requirements.txt"

    # ---- save
    with open(OUT / "exp2_per_draft.csv", "w", newline="", encoding="utf-8") as f:
        fields = [k for k in rows[0].keys() if k != "p_correct"] + ["p_correct"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "exp2_per_question.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys()))
        w.writeheader()
        w.writerows(qrows)

    n = len(rows)
    grounded = sum(r["quote_found"] and r["number_in_quote"] for r in rows)
    lab = [r for r in rows if r["correct"] != ""]
    experts = sum(q["decision"] == "expert check" for q in qrows)
    lines = [
        "# Experiment 2 - rule cards: results",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        "| Drafts scored | %d (%d questions) |" % (n, len(qrows)),
        "| Grounding: quote in PDF and number in quote | %d / %d (%.0f %%) |" % (grounded, n, 100.0 * grounded / n),
        "| Mean agreement across runs | %.2f |" % (sum(q["agreement"] for q in qrows) / len(qrows)),
        "| Accuracy against gold cards | %s |" % (("%d / %d (%.0f %%)" % (sum(r["correct"] for r in lab), len(lab), 100.0 * sum(r["correct"] for r in lab) / len(lab))) if lab else "no gold cards yet"),
        "| Cards sent to the expert (confidence < %.1f) | %d of %d |" % (APPROVE_AT, experts, len(qrows)),
        "| ML trust layer | %s |" % ml_text,
        "| Manual baseline (time to read the 10 clauses by hand) | fill in: ... minutes |",
        "",
        "| Question | Majority card | Gold | Agreement | Grounding | Accuracy | Confidence | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for q in qrows:
        lines.append("| %s | %s %s | %s | %.2f | %.2f | %s | %.2f | %s |" % (
            q["id"], q["majority_check"], q["majority_value"], q["gold_value"], q["agreement"],
            q["grounding"], q["accuracy"], q["confidence"], q["decision"]))
    (OUT / "exp2_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\nSaved: outputs/exp2_per_draft.csv, outputs/exp2_per_question.csv, outputs/exp2_summary.md")


if __name__ == "__main__":
    main()
