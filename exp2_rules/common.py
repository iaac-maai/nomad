"""Shared helpers for experiment 2 (rule cards)."""
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CHECKS = ["min_area", "fits_circle", "fits_square", "min_length",
          "min_height", "min_ratio", "max_count", "flag_is"]


def load_env():
    """Read .env from the repo root (keys stay out of the code)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        raise SystemExit("python-dotenv is missing. Run: pip install -r requirements.txt")
    env_file = ROOT / ".env"
    if not env_file.exists():
        raise SystemExit("No .env file. Copy .env.example to .env and fill in your keys.")
    load_dotenv(env_file)


def pdf_path():
    p = ROOT / os.getenv("REG_PDF", "data/regulations/decret_141_2012.pdf")
    if not p.exists():
        raise SystemExit("Regulation PDF not found: %s\nPut the PDF there or change REG_PDF in .env." % p)
    return p


def load_pdf_pages(path):
    """Return a list of page texts. Page numbers start at 1 (index 0 = page 1)."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def norm(text):
    """Lowercase, remove accents and punctuation, join hyphenated line breaks.
    Used to check if a quote really exists in the PDF."""
    text = text or ""
    text = text.replace("·", "")          # l·l -> ll
    text = re.sub(r"-\s*\n\s*", "", text)      # word-\nbreak -> wordbreak
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = text.replace("fi", "i").replace("fl", "l")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def light(text):
    """Lowercase and collapse spaces, but keep numbers like 2,80 or 1/8 intact."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()
