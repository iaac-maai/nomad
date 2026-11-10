"""NOMAD - download the law PDFs of the rulebook from their official sources and build the website's book pages.

The rulebook (the flipbook in "The laws") is 23 official documents compiled into one book with a cover, an index,
dividers and page numbers (Bhavini_NOMAD Files/02_Code/src/rulebook/compile_rulebook.py). The PDFs are not kept in
git: this script downloads each one from the body that publishes it (BOE, codigotecnico.org, Portal Jurídic de
Catalunya, Agència de l'Habitatge, RPUC, AMB, Ajuntament de Barcelona), then compiles the book into
Bhavini_NOMAD Files/04_Website/rulebook/parts/.

Page numbers: rulebook/index.json and rulebook/anchors.json (in git) were made from the versions downloaded in
October 2026. Consolidated laws are updated over time. The script compares every document's page count with
index.json and says which ones changed. Bookmarks in an unchanged document keep their place (moved by the pages
added before them); bookmarks in a changed text document are searched again in the new pages.

Needs: pip install pymupdf pillow   (about 190 MB of downloads, once)
Run from the repo root:  python tools/get_rulebook.py        (--check: only compare page counts, change nothing)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "Bhavini_NOMAD Files" / "02_Code"
DATA = CODE / "data"                                   # where compile_rulebook.py reads the PDFs (not in git)
BUILT = CODE / "results" / "rulebook"                  # where compile_rulebook.py writes the book (not in git)
SITE = ROOT / "Bhavini_NOMAD Files" / "04_Website" / "rulebook"

BOE = "https://www.boe.es/buscar/pdf/{y}/{id}-consolidado.pdf"
PJ = "https://portaljuridic.gencat.cat/eli/es-ct/{eli}/cat/pdf"
RPUC = "https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/documents?documentId={id}&downloadType=1&idioma=ca"
AMB = "https://docs.amb.cat/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node}/content/{name}?attachment=false&mimeType=application/pdf"
CIRC = "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/"

# short name (as in index.json) -> file read by compile_rulebook.py, official download URL
SOURCES = {
    "LOE": ("national/raw/BOE-A-1999-21567-consolidado.pdf", BOE.format(y=1999, id="BOE-A-1999-21567")),
    "CTE": ("national/raw/BOE-A-2006-5515-consolidado.pdf", BOE.format(y=2006, id="BOE-A-2006-5515")),
    "CTE DB-SUA": ("national/cte_db/DBSUA.pdf", "https://www.codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf"),
    "CTE DB-HS": ("national/cte_db/DBHS.pdf", "https://www.codigotecnico.org/pdf/Documentos/HS/DBHS.pdf"),
    "CTE DB-SI": ("national/cte_db/DBSI.pdf", "https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf"),
    "CTE DB-HR": ("national/cte_db/DBHR.pdf", "https://www.codigotecnico.org/pdf/Documentos/HR/DBHR.pdf"),
    "CTE DB-HE": ("national/cte_db/DBHE.pdf", "https://www.codigotecnico.org/pdf/Documentos/HE/DBHE.pdf"),
    "TRLSRU": ("national/raw/BOE-A-2015-11723-consolidado.pdf", BOE.format(y=2015, id="BOE-A-2015-11723")),
    "LDV": ("national/raw/BOE-A-2023-12203-consolidado.pdf", BOE.format(y=2023, id="BOE-A-2023-12203")),
    "LPH": ("national/raw/BOE-A-1960-10906-consolidado.pdf", BOE.format(y=1960, id="BOE-A-1960-10906")),
    "Decret 141/2012": ("catalonia/raw/D141-2012.pdf", PJ.format(eli="d/2012/10/30/141/con/20201212")),
    "Circular 10/2025": ("catalonia/raw/Circular-10-2025.pdf", CIRC + "CIRCULAR-NUM.-10-2025.pdf"),
    "Circular 8": ("catalonia/raw/Circular-08.pdf", CIRC + "Circular_informativa_8.pdf"),
    "Llei 18/2007": ("catalonia/raw/L18-2007.pdf", "portaljuridic:l/2007/12/28/18"),          # latest consolidated version
    "DL 50/2020": ("catalonia/raw/DLL50-2020.pdf", PJ.format(eli="dl/2020/12/09/50/con/20221101")),
    "TRLU": ("catalonia/raw/DL1-2010-TRLU.pdf", "portaljuridic:dlg/2010/08/03/1"),             # latest consolidated version
    "MPGM 1999 art. 225": ("pgm/raw/MPGM-1999-art225.pdf", RPUC.format(id=124324)),             # RPUC expedient 96749
    "MPGM 2004": ("pgm/raw/MPGM-2004-habitatges-parcela.pdf", RPUC.format(id=126035)),          # RPUC expedient 215050
    "MPGM B1600": ("pgm/raw/MPGM-B1600.pdf", RPUC.format(id=530003)),                           # RPUC expedient 283290
    "B1600 ruling": ("pgm/raw/MPGM-B1600-acord-sentencia-2022.pdf", RPUC.format(id=530002)),
    "OME": ("pgm/raw/OME.pdf", AMB.format(node="d33b31ee-fc6e-4ad9-bd5f-f997472e6609", name="Ordenances_edificacio.pdf")),
    "OM rehabilitació": ("pgm/raw/OM-rehabilitacio.pdf", AMB.format(node="1803f832-987f-4063-ac27-a0a4b93be792", name="Ordenances_rehabilitacio.pdf")),
    "Guia canvi d'ús": ("barcelona/raw/InforUrb_Canvi-us-habitatge.pdf",
                        "https://ajuntament.barcelona.cat/urbanisme-accio-climatica-mobilitat-pla-barris-serveis-urbans/sites/default/files/2025-03/InforUrb_Canvi-us-habitatge.pdf"),
}
UA = {"User-Agent": "NOMAD rulebook (IAAC MaAI research project; downloads each law once)"}


def fetch(url, timeout=600):
    """GET with the standard library. Some Generalitat servers (portaldogc.gencat.cat) still need the legacy TLS
    renegotiation that OpenSSL 3 refuses by default, so this context allows it; certificates are still checked."""
    import ssl, urllib.request
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def resolve(url):
    """portaljuridic:<eli> -> the PDF of the latest consolidated version, read from the law's ELI page"""
    import re
    if not url.startswith("portaljuridic:"):
        return url
    eli = url.split(":", 1)[1]
    page = fetch("https://portaljuridic.gencat.cat/eli/es-ct/" + eli, timeout=60).decode("utf-8", "replace")
    found = sorted(set(re.findall(r"/eli/es-ct/" + re.escape(eli) + r"/con/(\d{8})/cat/pdf", page)))
    if not found:
        raise RuntimeError("no consolidated PDF found on the ELI page of " + eli)
    return PJ.format(eli=f"{eli}/con/{found[-1]}")


def download():
    for short, (rel, url) in SOURCES.items():
        f = DATA / rel
        if f.exists() and f.stat().st_size > 1000:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        u = resolve(url)
        print(f"downloading {short:<20} {u[:110]}")
        body = fetch(u)
        if not body.startswith(b"%PDF"):
            raise RuntimeError(f"{short}: the server did not send a PDF ({u})")
        f.write_bytes(body)


def pages_now():
    import pymupdf
    return {short: pymupdf.open(DATA / rel).page_count for short, (rel, _) in SOURCES.items()}


def main():
    try:
        import pymupdf, PIL  # noqa: F401
    except ImportError:
        sys.exit("Needs pymupdf and pillow:  pip install pymupdf pillow")
    index = json.loads((SITE / "index.json").read_text(encoding="utf-8"))
    old_docs = {d["short"]: d for d in index["docs"]}
    download()
    now = pages_now()
    changed = [s for s in SOURCES if now[s] != old_docs[s]["pages"]]
    for s in SOURCES:
        print(f"  {s:<20} {now[s]:>4} pages" + ("" if s not in changed else f"   (was {old_docs[s]['pages']}: a newer consolidated version)"))
    if "--check" in sys.argv:
        return
    print("compiling the book (compile_rulebook.py) ...")
    subprocess.run([sys.executable, str(CODE / "src" / "rulebook" / "compile_rulebook.py")], cwd=CODE, check=True)
    new_index = json.loads((BUILT / "index.json").read_text(encoding="utf-8"))
    new_anch = json.loads((BUILT / "anchors.json").read_text(encoding="utf-8"))
    old_anch = json.loads((SITE / "anchors.json").read_text(encoding="utf-8"))
    new_start = {d["short"]: d["start"] for d in new_index["docs"]}
    merged = {}
    for k, a in old_anch.items():                          # unchanged document: same place, moved with its document
        if a["doc"] not in changed:
            merged[k] = dict(a, page=a["page"] - old_docs[a["doc"]]["start"] + new_start[a["doc"]])
        else:                                              # changed document: found again in the new pages
            merged[k] = new_anch[k]
            print(f"  bookmark {k}: searched again in the new {a['doc']} (page {merged[k]['page']})")
    parts = SITE / "parts"
    if parts.exists():
        shutil.rmtree(parts)
    shutil.copytree(BUILT / "parts", parts)
    (SITE / "index.json").write_text(json.dumps(new_index, ensure_ascii=False, indent=1), encoding="utf-8")
    (SITE / "anchors.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"book pages ready in {parts.relative_to(ROOT)} ({len(list(parts.glob('*.pdf')))} files, {new_index['pages']} pages)")
    if changed:
        print("changed since October 2026:", ", ".join(changed), "- index.json and anchors.json were updated; review them before committing.")


if __name__ == "__main__":
    main()
