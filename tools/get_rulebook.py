"""NOMAD - the law PDFs of the rulebook: download them from their official sources, pin their versions, build the book.

The rulebook (the flipbook in "The laws") is 23 official documents compiled into one book with a cover, an index,
dividers and page numbers (nomad/02_Code/src/rulebook/compile_rulebook.py). The PDFs are not kept in git: this script
downloads each one from the body that publishes it (BOE, codigotecnico.org, Portal Jurídic de Catalunya, Agència de
l'Habitatge, RPUC, AMB, Ajuntament de Barcelona) and builds the book into nomad/04_Website/rulebook/parts/.

Pinned versions: nomad/04_Website/rulebook/sources.lock.json (in git) holds, for every document, the URL of the version
used, its official version date (and what that date is based on), the download date, the file's sha256, the sha256 of
its normalised text (spaces, line-break hyphens and the Portal Jurídic page footer ignored) and one hash per article
(or per page, for documents without articles). A scan has no text, so for a scan the file's sha256 is what counts.

  python tools/get_rulebook.py            build the book from the pinned versions (downloads what is missing); stops if
                                          a downloaded file's text is not the pinned one
  python tools/get_rulebook.py --check    download today's official versions into 02_Code/data/_check/ and compare them
                                          with the lock: lists the articles that changed (with the words that changed
                                          when the pinned file is on this computer); changes nothing; exit code 2 if a
                                          text changed
  python tools/get_rulebook.py --accept   the same, then takes the new versions: updates the lock and rebuilds the book;
                                          bookmarks in unchanged documents move with their document, bookmarks in a
                                          changed document are searched again
Needs: pip install pymupdf pillow   (about 190 MB of downloads, once).  Run from the repo root.
"""
import datetime as dt
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "nomad" / "02_Code"
DATA = CODE / "data"                                   # where compile_rulebook.py reads the PDFs (not in git)
CHECK = DATA / "_check"                                # today's official versions, for --check / --accept (not in git)
BUILT = CODE / "results" / "rulebook"                  # where compile_rulebook.py writes the book (not in git)
SITE = ROOT / "nomad" / "04_Website" / "rulebook"
LOCK = SITE / "sources.lock.json"

BOE = "https://www.boe.es/buscar/pdf/{y}/{id}-consolidado.pdf"
PJ = "https://portaljuridic.gencat.cat/eli/es-ct/{eli}/cat/pdf"
RPUC = "https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/documents?documentId={id}&downloadType=1&idioma=ca"
AMB = "https://docs.amb.cat/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node}/content/{name}?attachment=false&mimeType=application/pdf"
CIRC = "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/"

# short name (as in index.json) -> file read by compile_rulebook.py, where today's official version is published
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
    "Decret 141/2012": ("catalonia/raw/D141-2012.pdf", "portaljuridic:d/2012/10/30/141"),
    "Circular 10/2025": ("catalonia/raw/Circular-10-2025.pdf", CIRC + "CIRCULAR-NUM.-10-2025.pdf"),
    "Circular 8": ("catalonia/raw/Circular-08.pdf", CIRC + "Circular_informativa_8.pdf"),
    "Llei 18/2007": ("catalonia/raw/L18-2007.pdf", "portaljuridic:l/2007/12/28/18"),
    "DL 50/2020": ("catalonia/raw/DLL50-2020.pdf", "portaljuridic:dl/2020/12/09/50"),
    "TRLU": ("catalonia/raw/DL1-2010-TRLU.pdf", "portaljuridic:dlg/2010/08/03/1"),
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
MONTHS = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}


# ---------------------------------------------------------------- downloading
def fetch(url, timeout=600, head=False):
    """GET (or HEAD) with the standard library -> (body, headers). Some Generalitat servers (portaldogc.gencat.cat)
    still need the legacy TLS renegotiation that OpenSSL 3 refuses by default; certificates are still checked."""
    import ssl, urllib.request
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    req = urllib.request.Request(url, headers=UA, method="HEAD" if head else "GET")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return (b"" if head else r.read()), dict(r.headers)


def resolve(url):
    """portaljuridic:<eli> -> the PDF of the latest consolidated version, read from the law's ELI page"""
    if not url.startswith("portaljuridic:"):
        return url
    eli = url.split(":", 1)[1]
    page = fetch("https://portaljuridic.gencat.cat/eli/es-ct/" + eli, timeout=60)[0].decode("utf-8", "replace")
    found = sorted(set(re.findall(r"/eli/es-ct/" + re.escape(eli) + r"/con/(\d{8})/cat/pdf", page)))
    if not found:
        raise RuntimeError("no consolidated PDF found on the ELI page of " + eli)
    return PJ.format(eli=f"{eli}/con/{found[-1]}")


def get(url, dest, short):
    body, headers = fetch(url)
    if not body.startswith(b"%PDF"):
        raise RuntimeError(f"{short}: the server did not send a PDF ({url})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return headers


# ---------------------------------------------------------------- what a version is
def fold(s):
    s = unicodedata.normalize("NFKC", s).replace("\u00ad", "").replace("’", "'")
    s = re.sub(r"Portal Jurídic de Catalunya\s*\n\s*\d+\s*\n", "\n", s)          # the page footer of the Portal Jurídic
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)                                   # a word split at the end of a line
    return re.sub(r"\s+", " ", s).strip()


HEAD = re.compile(r"^(?:(?:Article|Artículo|Art\.)\s+\d+(?:\s*(?:bis|ter|quater|quinquies))?|"
                  r"Disposici[óo] (?:addicional|adicional|transitòria|transitoria|derogatòria|derogatoria|final)\s+\S+)"
                  r"\.?(?:\s+[A-ZÀ-ÚÇ].{0,140})?$")
NOTE = re.compile(r"modificat|afegit|derogat|deixa|modificad|añadid|suprimid|redacció|redacción", re.I)


def units(path):
    """the document as {article (or 'page N'): normalised text}, and whether it is a scan"""
    import pymupdf
    pages = [p.get_text() for p in pymupdf.open(path)]
    if len(fold(" ".join(pages))) < 500:
        return {}, True
    out, key, seen = {}, None, {}
    for n, t in enumerate(pages, 1):
        for line in t.split("\n"):
            s = line.strip()
            if HEAD.match(s) and not NOTE.search(s):
                k = re.match(r"^(\S+\s+\d+(?:\s*(?:bis|ter|quater|quinquies))?|Disposici[óo] \S+ \S+)", s).group(1)
                k = re.sub(r"\s+", " ", k).rstrip(".")
                seen[k] = seen.get(k, 0) + 1
                key = k if seen[k] == 1 else f"{k} ({seen[k]})"
            out.setdefault(key or "(before the first article)", []).append(line)
    if len(out) < 4:                                       # no article structure (CTE documents, circulars, guide): pages
        return {f"page {n}": fold(t) for n, t in enumerate(pages, 1)}, False
    return {k: fold("\n".join(v)) for k, v in out.items()}, False


def h(b):
    return hashlib.sha256(b).hexdigest()


def fingerprint(path):
    u, scan = units(path)
    import pymupdf
    return {"sha256": h(path.read_bytes()), "pages": pymupdf.open(path).page_count,
            "text_sha256": None if scan else h(" ".join(u[k] for k in u).encode("utf-8")),
            "articles": {k: h(v.encode("utf-8"))[:16] for k, v in u.items()}}


def version(short, url, path, headers):
    """the document's own version date and what it is based on"""
    import pymupdf
    t = " ".join(p.get_text() for p in pymupdf.open(path))
    m = re.search(r"Vigència\s*(\d{2})/(\d{2})/(\d{4})", t)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}", "Vigència of the consolidated text (Portal Jurídic)"
    m = re.search(r"Última modificación:\s*(\d{1,2}) de (\w+) de (\d{4})", t)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}", "Última modificación of the consolidated text (BOE)"
    if short.startswith("Circular"):
        m = re.search(r"(20\d{2})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}", t)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "date of the digital signature"
    m = re.search(r"/files/(\d{4})-(\d{2})/", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}", "month in the Ajuntament's URL"
    m = re.search(r"documentId=(\d+)", url)
    if "RPUC" in url and m:
        return None, f"RPUC document {m.group(1)} (the scan carries no date)"
    lm = (headers or {}).get("Last-Modified")
    if lm:
        return dt.datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT").date().isoformat(), "server date of the file (Last-Modified)"
    return None, "no date found"


def entry(short, url, path, headers, downloaded):
    d, basis = version(short, url, path, headers)
    return dict(url=url, version_date=d, version_basis=basis, downloaded=downloaded, **fingerprint(path))


# ---------------------------------------------------------------- comparing
def words_changed(old_path, new_path, keys, limit=6):
    """the words that changed in each changed article (needs the pinned file on this computer)"""
    a, _ = units(old_path)
    b, _ = units(new_path)
    for k in keys:
        x, y = a.get(k, "").split(), b.get(k, "").split()
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes()[:200]:
            if op != "equal" and limit:
                limit -= 1
                print(f"        {k}: «{' '.join(x[max(0, i1 - 8):i2 + 4])}»\n          now «{' '.join(y[max(0, j1 - 8):j2 + 4])}»")


def compare(lock, short, new):
    """-> None if the text is the pinned one, else a short report"""
    old = lock["docs"][short]
    same = (new["text_sha256"] == old["text_sha256"]) if old["text_sha256"] else (new["sha256"] == old["sha256"])
    if same:
        return None
    oa, na = old["articles"], new["articles"]
    changed = [k for k in na if k in oa and na[k] != oa[k]]
    return {"changed": changed, "added": [k for k in na if k not in oa], "removed": [k for k in oa if k not in na],
            "scan": not old["text_sha256"]}


def report(short, old, new, diff, old_path, new_path):
    print(f"\n  CHANGED  {short}: version {old['version_date']} -> {new['version_date']} ({new['version_basis']}), "
          f"{old['pages']} -> {new['pages']} pages")
    if diff["scan"]:
        print("        a scan (no text): the file is different; compare the pages by eye")
        return
    for what in ("changed", "added", "removed"):
        if diff[what]:
            print(f"        {what}: {', '.join(diff[what][:40])}{' …' if len(diff[what]) > 40 else ''}")
    if old_path.exists():
        words_changed(old_path, new_path, diff["changed"])
    else:
        print("        (the pinned file is not on this computer, so only the articles are listed)")


# ---------------------------------------------------------------- the book
def build(lock, changed_docs):
    print("compiling the book (compile_rulebook.py) ...")
    index = json.loads((SITE / "index.json").read_text(encoding="utf-8"))
    old_docs = {d["short"]: d for d in index["docs"]}
    subprocess.run([sys.executable, str(CODE / "src" / "rulebook" / "compile_rulebook.py")], cwd=CODE, check=True)
    new_index = json.loads((BUILT / "index.json").read_text(encoding="utf-8"))
    new_anch = json.loads((BUILT / "anchors.json").read_text(encoding="utf-8"))
    old_anch = json.loads((SITE / "anchors.json").read_text(encoding="utf-8"))
    moved = {d["short"] for d in new_index["docs"] if d["pages"] != old_docs[d["short"]]["pages"]} | set(changed_docs)
    new_start = {d["short"]: d["start"] for d in new_index["docs"]}
    merged = {}
    for k, a in old_anch.items():                          # unchanged document: same place, moved with its document
        if a["doc"] not in moved:
            merged[k] = dict(a, page=a["page"] - old_docs[a["doc"]]["start"] + new_start[a["doc"]])
        else:                                              # changed document: found again in the new pages
            merged[k] = new_anch[k]
            print(f"  bookmark {k}: searched again in the new {a['doc']} (page {merged[k]['page']})")
    parts = SITE / "parts"
    if parts.exists():
        shutil.rmtree(parts)
    shutil.copytree(BUILT / "parts", parts)
    (SITE / "anchors.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    stamp(lock, new_index)
    print(f"book pages ready in {parts.relative_to(ROOT)} ({len(list(parts.glob('*.pdf')))} files, {new_index['pages']} pages)")


def stamp(lock, index=None):
    """write the lock's dates into index.json, for the website: 'Law texts as of …' and a version next to each document"""
    index = index or json.loads((SITE / "index.json").read_text(encoding="utf-8"))
    index["as_of"] = lock["as_of"]
    for d in index["docs"]:
        e = lock["docs"][d["short"]]
        d["version_date"], d["version_basis"] = e["version_date"], e["version_basis"]
    (SITE / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def save(lock):
    lock["as_of"] = max(e["downloaded"] for e in lock["docs"].values())
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- the three runs
def run_build(lock):
    """build from the pinned versions; never takes a version that is not in the lock"""
    bad = []
    for short, (rel, _) in SOURCES.items():
        f, pin = DATA / rel, lock["docs"][short]
        if not (f.exists() and f.stat().st_size > 1000):
            print(f"downloading {short:<20} {pin['url'][:100]}")
            try:
                get(pin["url"], f, short)
            except Exception as e:                         # e.g. an old consolidated version no longer served
                print(f"  could not download the pinned version: {e}")
                bad.append(short); continue
        if compare(lock, short, fingerprint(f)):
            bad.append(short)
    if bad:
        print("\nSTOP: not the pinned version of", ", ".join(bad), "\nRun  python tools/get_rulebook.py --check  to see "
              "what changed, then  --accept  if the new text is fine.")
        sys.exit(2)
    build(lock, [])


def run_check(lock, accept):
    """compare today's official versions with the lock; with accept, take them and rebuild"""
    today = dt.date.today().isoformat()
    changes = {}
    for short, (rel, src) in SOURCES.items():
        url = resolve(src)
        new_path = CHECK / rel
        headers = get(url, new_path, short)
        new = entry(short, url, new_path, headers, today)
        old = lock["docs"][short]
        diff = compare(lock, short, new)
        if diff:
            changes[short] = (new, new_path)
            report(short, old, new, diff, DATA / rel, new_path)
        else:
            print(f"  same     {short:<20} {old['version_date'] or '-':<10} {old['version_basis']}")
            if accept and new["sha256"] != old["sha256"]:      # same text, new file (re-signed, re-generated): keep the new bytes
                old.update(sha256=new["sha256"], url=url)
    if not changes:
        print("\nEvery official text is the pinned one.")
        if accept:
            save(lock)
        return
    if not accept:
        print(f"\n{len(changes)} official text(s) changed. Nothing was changed here. If the new texts are fine:  "
              "python tools/get_rulebook.py --accept")
        sys.exit(2)
    for short, (new, new_path) in changes.items():
        shutil.copyfile(new_path, DATA / SOURCES[short][0])
        lock["docs"][short] = new
    save(lock)
    build(lock, list(changes))
    print("accepted:", ", ".join(changes), "- the lock, index.json and anchors.json changed: review them before committing.")


def run_init():
    """write the lock from the PDFs on this computer (once, from the versions the book was built with)"""
    lock = {"about": "The versions of the 23 law PDFs in the rulebook. Written by tools/get_rulebook.py; change it only "
                     "with --accept.", "docs": {}}
    for short, (rel, src) in SOURCES.items():
        url = resolve(src)
        _, headers = fetch(url, timeout=60, head=True)
        f = DATA / rel
        lock["docs"][short] = entry(short, url, f, headers, dt.date.fromtimestamp(f.stat().st_mtime).isoformat())
        print(f"  {short:<20} {lock['docs'][short]['version_date'] or '-':<10} {lock['docs'][short]['version_basis']}")
    save(lock)
    stamp(lock)


def main():
    try:
        import pymupdf, PIL  # noqa: F401
    except ImportError:
        sys.exit("Needs pymupdf and pillow:  pip install pymupdf pillow")
    if "--init" in sys.argv:
        return run_init()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if "--check" in sys.argv or "--accept" in sys.argv:
        return run_check(lock, "--accept" in sys.argv)
    run_build(lock)


if __name__ == "__main__":
    main()
