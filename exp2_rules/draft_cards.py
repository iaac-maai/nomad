"""Experiment 2, step 1: let the AI draft rule cards.

For each question in questions.csv:
  1. find the most relevant pieces of the regulation (from the PDF, or from open-notebook),
  2. ask the LLM to fill one rule card as JSON,
  3. repeat 5 times (to measure how consistent it is).
Everything is saved to outputs/drafts.jsonl. Run it again and it continues where it stopped.

Run from the repo root:
    python exp2_rules/draft_cards.py              # all questions, 5 runs each
    python exp2_rules/draft_cards.py --only Q01   # one question (good first test)
    python exp2_rules/draft_cards.py --fresh      # delete old drafts and start again
"""
import argparse
import csv
import json
import os
import re
import time

import requests

from common import CHECKS, OUT, ROOT, load_env, load_pdf_pages, norm, pdf_path

PROMPT = """You are reading Catalan / Spanish housing regulations (Decret 141/2012 and related texts).
Fill ONE rule card as JSON for this question.

Question: {topic}
Scope: {annex}

Use ONLY the excerpts below. Do not use your own memory of the law.
If the excerpts do not contain the answer, return {{"check": "not_found"}}.

Allowed values for "check": {checks}, not_found.
Write ratios and percentages as decimals (1/8 -> 0.125, 10 % -> 0.10).

Return only JSON with these keys:
  "check": one allowed value,
  "value": a number,
  "unit": "m2", "m", "ratio", "count" or "bool",
  "quote": the exact words from the excerpt that give the value (max 40 words, original language, copied character by character),
  "page": the page number shown before the excerpt,
  "applies_to": a few words on what the rule applies to.

Excerpts:
{context}
"""


# ---------------------------------------------------------------- retrieval
def pdf_chunks(pages, size=120, step=80):
    """Cut every page into overlapping windows of ~120 words, remembering the page number."""
    chunks = []
    for i, text in enumerate(pages):
        words = text.split()
        if not words:
            continue
        for start in range(0, max(1, len(words) - size + step), step):
            piece = " ".join(words[start:start + size])
            chunks.append({"page": i + 1, "text": piece, "norm": norm(piece).split()})
    return chunks


def retrieve_pdf(query, chunks, k):
    """Very simple keyword search: count how many query words (by their first 5 letters) appear."""
    prefixes = [w[:5] for w in norm(query).split() if len(w) >= 4]
    scored = []
    for ch in chunks:
        hits = sum(1 for p in prefixes if any(w.startswith(p) for w in ch["norm"]))
        if hits:
            scored.append((hits, -ch["page"], ch))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [{"page": c["page"], "text": c["text"]} for _, _, c in scored[:k]]


def retrieve_notebook(query, k):
    """Vector search in open-notebook (Docker must be running, PDFs must be uploaded)."""
    url = os.getenv("OPEN_NOTEBOOK_URL", "http://localhost:5055").rstrip("/") + "/api/search"
    headers = {}
    if os.getenv("OPEN_NOTEBOOK_PASSWORD"):
        headers["Authorization"] = "Bearer " + os.getenv("OPEN_NOTEBOOK_PASSWORD")
    body = {"query": query, "type": "vector", "limit": k,
            "search_sources": True, "search_notes": False}
    r = requests.post(url, json=body, headers=headers, timeout=60)
    r.raise_for_status()
    out = []
    for item in r.json().get("results", []):
        text = item.get("content") or item.get("highlight") or ""
        if isinstance(text, list):
            text = " ".join(map(str, text))
        out.append({"page": None, "text": str(text), "source": item.get("title")})
    return out


# ---------------------------------------------------------------- LLM calls
def post_with_retry(url, headers, body, tries=8):
    for attempt in range(tries):
        wait = min(60, 10 * (attempt + 1))
        try:
            r = requests.post(url, headers=headers, json=body, timeout=180)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            print("    no answer from the server, waiting %ss..." % wait)
            time.sleep(wait)
            continue
        if r.status_code in (429, 500, 502, 503, 529):
            print("    server busy (%s), waiting %ss..." % (r.status_code, wait))
            time.sleep(wait)
            continue
        if r.status_code in (400, 401, 403, 404):
            raise SystemExit("Stopped: HTTP %s. Check the API key and the model name in .env.\n%s"
                             % (r.status_code, r.text[:400]))
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s: %s" % (r.status_code, r.text[:400]))
        return r.json()
    raise RuntimeError("gave up after %d tries" % tries)

def call_anthropic(prompt):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is empty in .env")
    data = post_with_retry(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 800,
         "temperature": 1.0, "messages": [{"role": "user", "content": prompt}]})
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def call_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY is empty in .env")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    data = post_with_retry(
        "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
        {"x-goog-api-key": key, "content-type": "application/json"},
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}})
    parts = data["candidates"][0]["content"].get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def parse_card(text):
    """Take the first {...} block in the answer and read it as JSON."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        card = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if "value" in card:
        try:
            card["value"] = float(str(card["value"]).replace(",", "."))
        except (TypeError, ValueError):
            card["value"] = None
    return card


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--only", default="", help="comma separated ids, e.g. Q01,Q02")
    ap.add_argument("--k", type=int, default=5, help="how many excerpts to give the AI")
    ap.add_argument("--fresh", action="store_true", help="delete old drafts first")
    args = ap.parse_args()

    load_env()
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    retrieval = os.getenv("RETRIEVAL", "pdf").strip().lower()
    model = os.getenv("ANTHROPIC_MODEL" if provider == "anthropic" else "GEMINI_MODEL", "")
    call = call_anthropic if provider == "anthropic" else call_gemini

    with open(ROOT / "exp2_rules" / "questions.csv", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        questions = [q for q in questions if q["id"] in wanted]

    chunks = None
    if retrieval == "pdf":
        pages = load_pdf_pages(pdf_path())
        chunks = pdf_chunks(pages)
        print("PDF loaded: %d pages, %d chunks" % (len(pages), len(chunks)))
        if sum(len(p) for p in pages) < 1000:
            print("WARNING: almost no text in the PDF. It may be a scanned image; use another PDF.")

    OUT.mkdir(exist_ok=True)
    out_file = OUT / "drafts.jsonl"
    if args.fresh and out_file.exists():
        out_file.unlink()
    done = set()
    if out_file.exists():
        for line in open(out_file, encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("card") is not None and rec.get("provider") == provider and rec.get("model") == model:
                done.add((rec["id"], rec["run"]))

    print("Provider: %s (%s) | retrieval: %s | %d questions x %d runs"
          % (provider, model, retrieval, len(questions), args.runs))
    for q in questions:
        context = (retrieve_pdf(q["query"], chunks, args.k) if retrieval == "pdf"
                   else retrieve_notebook(q["query"], args.k))
        if not context:
            print("%s: no excerpts found, check the query in questions.csv" % q["id"])
        ctx_text = "\n\n".join("[page %s] %s" % (c.get("page") or "?", c["text"]) for c in context)
        prompt = PROMPT.format(topic=q["topic_en"], annex=q.get("annex", ""),
                               checks=", ".join(CHECKS), context=ctx_text)
        for run in range(1, args.runs + 1):
            if (q["id"], run) in done:
                continue
            raw, card, error = "", None, None
            try:
                raw = call(prompt)
                card = parse_card(raw)
                if card is None:
                    error = "answer was not valid JSON"
            except RuntimeError as e:
                error = str(e)
            rec = {"id": q["id"], "run": run, "provider": provider, "model": model,
                   "retrieval": retrieval, "card": card, "raw": raw, "error": error,
                   "context_pages": [c.get("page") for c in context]}
            with open(out_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if card:
                v = card.get("value")
                short = "%s %s %s" % (card.get("check"), ("%g" % v) if isinstance(v, float) else v, card.get("unit"))
            else:
                short = error
            print("%s run %d: %s" % (q["id"], run, short))
    print("\nSaved to %s\nNext: fill exp2_rules/gold_cards.csv, then run python exp2_rules/score_cards.py" % out_file)


if __name__ == "__main__":
    main()
