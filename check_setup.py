"""Run this first: python check_setup.py
It tells you, line by line, what is ready and what is still missing."""
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ok = True


def line(good, text, fix=""):
    global ok
    ok = ok and good
    print(("  OK    " if good else "  MISSING ") + text + ("" if good or not fix else "  ->  " + fix))


print("Python %s" % sys.version.split()[0])
line(sys.version_info >= (3, 10), "Python 3.10 or newer", "install Python 3.12 from python.org")
line(sys.prefix != sys.base_prefix, "running inside the .venv",
     "activate it: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Mac)")

for mod, pip_name in [("requests", "requests"), ("dotenv", "python-dotenv"), ("pypdf", "pypdf"),
                      ("pandas", "pandas"), ("numpy", "numpy"), ("sklearn", "scikit-learn"),
                      ("xgboost", "xgboost"), ("matplotlib", "matplotlib")]:
    try:
        importlib.import_module(mod)
        line(True, "package " + pip_name)
    except ImportError:
        line(False, "package " + pip_name, "pip install -r requirements.txt")

env = ROOT / ".env"
line(env.exists(), ".env file", "copy .env.example to .env and fill in your keys")
if env.exists():
    from dotenv import load_dotenv
    load_dotenv(env)
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    key = "ANTHROPIC_API_KEY" if provider == "anthropic" else "GEMINI_API_KEY"
    line(bool(os.getenv(key)), "%s is set (provider: %s)" % (key, provider), "paste your key into .env")
    pdf = ROOT / os.getenv("REG_PDF", "data/regulations/decret_141_2012.pdf")
    line(pdf.exists(), "regulation PDF at %s" % pdf.relative_to(ROOT), "download it, see data/regulations/README.md")
    if os.getenv("RETRIEVAL", "pdf") == "notebook":
        try:
            import requests
            r = requests.get(os.getenv("OPEN_NOTEBOOK_URL", "http://localhost:5055") + "/health", timeout=5)
            line(r.status_code < 500, "open-notebook API answers")
        except Exception:
            line(False, "open-notebook API answers", "start Docker and run: docker compose up -d")

print("\nAll good, you can start." if ok else "\nFix the MISSING lines, then run this again.")
