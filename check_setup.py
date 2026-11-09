"""Run this first: python check_setup.py
It tells you, line by line, what is ready and what is still missing to open and rebuild the NOMAD website."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "Bhavini_NOMAD Files" / "04_Website"
ok = True


def line(good, text, fix="", needed=True):
    global ok
    ok = ok and (good or not needed)
    print(("  OK      " if good else "  MISSING " if needed else "  OPTIONAL ") + text + ("" if good or not fix else "  ->  " + fix))


print("Python %s" % sys.version.split()[0])
line(sys.version_info >= (3, 10), "Python 3.10 or newer", "install Python 3.12 from python.org")
line((SITE / "index.html").exists() and (SITE / "data" / "premises.json").exists(), "the website and its data",
     "clone the repo again: the files under Bhavini_NOMAD Files/04_Website are in git")
for mod, pip_name, why in [("pymupdf", "pymupdf", "to build the rulebook pages"), ("PIL", "pillow", "to build the rulebook pages")]:
    try:
        importlib.import_module(mod)
        line(True, f"package {pip_name} ({why})")
    except ImportError:
        line(False, f"package {pip_name} ({why})", "pip install -r requirements.txt", needed=False)
line((SITE / "rulebook" / "parts").exists(), "rulebook pages built", "python tools/get_rulebook.py (or just python serve.py)", needed=False)
print("\nAll good: python serve.py opens the site." if ok else "\nFix the MISSING lines, then run this again.")
