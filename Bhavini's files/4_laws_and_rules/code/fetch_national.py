"""Nomad - Step 1a: download Spain's national laws from the BOE open-data API
and split them into article chunks for RAG."""
import json, os, time
import xml.etree.ElementTree as ET
import requests
import pandas as pd

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
OUT = "4_laws_and_rules/input/national"

NORMS = [
    {"id": "BOE-A-2006-5515",  "short": "CTE",    "why": "Technical building code (Part I)"},
    {"id": "BOE-A-1999-21567", "short": "LOE",    "why": "Building Act"},
    {"id": "BOE-A-2015-11723", "short": "TRLSRU", "why": "Land & urban rehabilitation law"},
    {"id": "BOE-A-2023-12203", "short": "LDV",    "why": "Right to Housing law 2023"},
    {"id": "BOE-A-1960-10906", "short": "LPH",    "why": "Horizontal Property law"},
]

def get_json(url):
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()

def get_xml(url):
    r = requests.get(url, headers={"Accept": "application/xml"}, timeout=120)
    r.raise_for_status()
    return r.text

def xml_to_chunks(xml_text, norm):
    root = ET.fromstring(xml_text)
    chunks = []
    for b in root.iter("bloque"):
        versions = b.findall("version")
        if not versions:
            continue
        v = versions[-1]
        parts = []
        for el in v:
            if el.tag == "p":
                parts.append("".join(el.itertext()).strip())
            elif el.tag == "table":
                for tr in el.iter("tr"):
                    cells = [" ".join(td.itertext()).strip() for td in tr]
                    parts.append(" | ".join(cells))
        text = "\n".join(p for p in parts if p)
        if not text:
            continue
        chunks.append({
            "norm_id": norm["id"], "norm": norm["short"], "level": "national",
            "block_id": b.get("id"), "block_type": b.get("tipo"), "title": b.get("titulo"),
            "in_force_from": v.get("fecha_vigencia"),
            "source_url": f"https://www.boe.es/buscar/act.php?id={norm['id']}#{b.get('id')}",
            "text": text,
        })
    return chunks

def main():
    os.makedirs(OUT, exist_ok=True)
    all_chunks, rows = [], []
    for n in NORMS:
        print("Downloading", n["short"], n["id"])
        meta = get_json(f"{API}/id/{n['id']}/metadatos")["data"]
        meta = meta[0] if isinstance(meta, list) else meta
        xml_text = get_xml(f"{API}/id/{n['id']}/texto")
        with open(f"{OUT}/{n['id']}.xml", "w", encoding="utf-8") as f:
            f.write(xml_text)
        chunks = xml_to_chunks(xml_text, n)
        all_chunks += chunks
        rows.append({"id": n["id"], "short": n["short"], "title": meta.get("titulo"),
                     "last_update": meta.get("fecha_actualizacion"),
                     "articles": len(chunks), "why": n["why"]})
        time.sleep(1)
    # one file per source; 4_laws_and_rules/code/build_rulebook.py merges them into chunks.jsonl
    with open(f"{OUT}/boe_chunks.jsonl", "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/summary.csv", index=False)
    print(df[["short", "articles", "last_update"]])
    print("Total chunks:", len(all_chunks))

if __name__ == "__main__":
    main()
