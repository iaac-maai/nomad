"""Open a NOMAD site on this computer: python serve.py [--site bhavini|bars]

The default site is Bhavini's official site. Use --site bars for Bars's previous site. The first time, it may download
law PDFs and build the book (needs `pip install pymupdf pillow`). Without them the whole site works except
the pages of "The laws". Then it serves the site at http://localhost:8000 and opens it in the browser.
Stop it with Ctrl+C.   Options: --port 8001, --no-browser, --no-rulebook
"""
import functools
import http.server
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITES = {
    "bhavini": ROOT / "Bhavini's files" / "app",
    "bars": ROOT / "Bars's files" / "app",
}


def main():
    args = sys.argv[1:]
    site_name = args[args.index("--site") + 1] if "--site" in args else "bhavini"
    if site_name not in SITES:
        raise SystemExit("--site must be bhavini or bars")
    SITE = SITES[site_name]
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8000
    if site_name == "bars" and not (SITE / "rulebook" / "parts").exists() and "--no-rulebook" not in args:
        try:
            import pymupdf, PIL  # noqa: F401
            print("First run: downloading the law PDFs and building the rulebook pages (a few minutes) ...")
            subprocess.run([sys.executable, str(ROOT / "Bars's files" / "4_laws_and_rules" / "code" / "get_rulebook.py")], check=True)
        except ImportError:
            print("The rulebook pages are not built yet. To see them: pip install pymupdf pillow, then run python serve.py again.")
        except subprocess.CalledProcessError:
            print("Building the rulebook failed (see above). The rest of the site works; try again later.")
    if site_name == "bhavini" and not (SITE / "rulebook" / "parts").exists() and "--no-rulebook" not in args:
        print("Bhavini's rulebook pages are not built; serving the site without changing her files.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        url = f"http://localhost:{port}/"
        print(f"NOMAD ({site_name}) is running at {url}  (Ctrl+C to stop)")
        if "--no-browser" not in args:
            webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


if __name__ == "__main__":
    main()
