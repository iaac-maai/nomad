"""Open the NOMAD website on this computer:   python serve.py

The first time, it downloads the law PDFs from their official sources and builds the rulebook's pages
(tools/get_rulebook.py, about 190 MB, needs `pip install pymupdf pillow`). Without them the whole site works except
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
SITE = ROOT / "nomad" / "04_Website"


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
    if not (SITE / "rulebook" / "parts").exists() and "--no-rulebook" not in sys.argv:
        try:
            import pymupdf, PIL  # noqa: F401
            print("First run: downloading the law PDFs and building the rulebook pages (a few minutes) ...")
            subprocess.run([sys.executable, str(ROOT / "tools" / "get_rulebook.py")], check=True)
        except ImportError:
            print("The rulebook pages are not built yet. To see them: pip install pymupdf pillow, then run python serve.py again.")
        except subprocess.CalledProcessError:
            print("Building the rulebook failed (see above). The rest of the site works; try again later.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        url = f"http://localhost:{port}/"
        print(f"NOMAD is running at {url}  (Ctrl+C to stop)")
        if "--no-browser" not in sys.argv:
            webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


if __name__ == "__main__":
    main()
