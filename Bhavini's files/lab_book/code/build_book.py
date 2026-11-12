"""Nomad - build the lab book page (lab_book/site/index.html) from lab_book/experiments.json and lab_book/figures/.

Numbers written as {name} in the entries are filled from our result files (metrics() below),
so the book always shows the latest run. Figures are copied next to the page.
Run after every experiment:
  .venv/Scripts/python lab_book/code/make_figures.py
  .venv/Scripts/python lab_book/code/build_book.py
Then publish lab_book/site/index.html with the figures (the results page links to it).
"""
import csv, glob, html, json, shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "lab_book"
SITE = BOOK / "site"
DASH = ROOT / "8_report_and_city/output/dashboard/dashboard_data"


def pct(v):
    return f"{float(v):.0%}"


def metrics():
    m = {}
    for r in csv.DictReader(open(DASH / "headline.csv", encoding="utf-8")):
        v = float(r["value"])
        m[r["metric"]] = pct(v) if v < 1 else f"{v:,.0f}"
    ev = json.load(open(ROOT / "2_building/output/plan_reading/eval_summary.json"))
    m["reader_iou_given"] = f"{ev['scale given']['median_iou']:.2f}"
    m["reader_area10_given"] = pct(ev["scale given"]["area_within_10pct"])
    m["reader_scale_err"] = pct(ev["scale estimated"]["median_scale_error"])
    for f in glob.glob(str(ROOT / "2_building/output/plan_reading/compare/*.json")):
        plans, walls = Path(f).stem.split("__")
        d = json.load(open(f))["scale given"]
        m[f"race_{walls}_{'messy' if 'messy' in plans else 'clean'}"] = pct(d["area_within_10pct"])
    f5 = ROOT / "6_check_the_shop/output/summary.json"
    if f5.exists():
        s5 = json.load(open(f5, encoding="utf-8"))
        v = s5["2 x 1-bed + 1 x 2-bed"]
        m.update(s5_yes=str(v["verdicts"].get("YES", 0)), s5_partly=str(v["verdicts"].get("PARTLY", 0)), s5_no=str(v["verdicts"].get("NO", 0)),
                 s5_fit_fail=str(v["cards_failed"].get("Flats that fit", 0)), s5_dark20=str(s5["daylight"]["shops_with_over_20pct_dark"]))
    f6 = ROOT / "7_floor_plans/output/generation/stage6_summary.json"
    if f6.exists():
        s6 = json.load(open(f6, encoding="utf-8"))
        v, w = s6["2 x 1-bed + 1 x 2-bed"], s6["5 x 1-bed + 2 x 2-bed"]
        m.update(s6_works_v1=str(v["works_v1"]), s6_works_after=str(v["works_after"]), s6_flats_v1=str(v["passing_flats_v1"]),
                 s6_flats_after=str(v["passing_flats_after"]), s6_flats_v1_big=str(w["passing_flats_v1"]), s6_flats_after_big=str(w["passing_flats_after"]))
    fi = ROOT / "7_floor_plans/output/generation/iterations_summary.json"
    if fi.exists():
        si = json.load(open(fi, encoding="utf-8"))
        f5, it = si["stage5_flags_as_it_is"], si["iterations"]
        m.update(it_flag_yes=str(f5.get("YES", 0)), it_flag_partly=str(f5.get("PARTLY", 0)), it_flag_no=str(f5.get("NO", 0)),
                 it1_homes=str(it["1 as asked"]["homes"]), it2_homes=str(it["2 as asked, compact rooms"]["homes"]),
                 it3_homes=str(it["3 most homes"]["homes"]), it3_yes=str(it["3 most homes"]["verdicts"].get("YES", 0)),
                 it3_any=str(it["3 most homes"]["shops_with_at_least_one_home"]))
    m["repos_found"] = str(sum(1 for _ in csv.DictReader(open(ROOT / "docs/github_repos.csv", encoding="utf-8"))))
    return m


def fill(text, m):
    for k, v in m.items():
        text = text.replace("{" + k + "}", v)
    return html.escape(text)


CSS = """
:root {
  /* layout: drawing-sheet entries in one reading column, a sticky sheet index on wide screens */
  --paper: #f7f8f6; --sheet: #ffffff; --ink: #1d2733; --muted: #5d6874; --rule: #d9ded9;
  --blue: #2c5d8f; --ochre: #b57a1f; --wash: #eef3f8;
  --display: "Archivo", "Arial Narrow", system-ui, sans-serif;
  --body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #11161c; --sheet: #181f27; --ink: #e6e9ec; --muted: #9aa5b1; --rule: #2b3540;
  --blue: #7fb0e3; --ochre: #e0a955; --wash: #1d2836; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #11161c; --sheet: #181f27; --ink: #e6e9ec; --muted: #9aa5b1; --rule: #2b3540;
  --blue: #7fb0e3; --ochre: #e0a955; --wash: #1d2836; color-scheme: dark }
* { box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font: 16px/1.6 var(--body); margin: 0; }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 40px 80px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 48px; }
@media (max-width: 860px) { .wrap { grid-template-columns: minmax(0, 1fr); gap: 24px; } nav.index { position: static !important; } }
header.book { grid-column: 1 / -1; display: grid; gap: 10px; border-bottom: 2px solid var(--ink); padding-bottom: 22px; }
.eyebrow { font: 600 12px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--blue); }
h1 { font: 700 clamp(40px, 6vw, 68px)/1 var(--display); letter-spacing: -.01em; margin: 0; text-wrap: balance; }
.lede { max-width: 62ch; color: var(--muted); margin: 0; }
.meta { font: 13px/1.4 var(--mono); color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px 20px; }
nav.index { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 20px); align-self: start; display: grid; gap: 2px; }
nav.index .h { font: 600 11px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
nav.index a { display: grid; grid-template-columns: 36px 1fr; gap: 8px; padding: 6px 8px; border-radius: 4px; color: var(--ink); text-decoration: none; font-size: 14px; line-height: 1.3; }
nav.index a:hover, nav.index a:focus-visible { background: var(--wash); outline: none; }
nav.index a span:first-child { font: 600 12px/1.4 var(--mono); color: var(--blue); }
main { display: grid; gap: 56px; min-width: 0; }
article.sheet { background: var(--sheet); border: 1px solid var(--rule); min-width: 0; }
.block { display: grid; grid-template-columns: 90px repeat(2, minmax(0, 1fr)); border-bottom: 1px solid var(--rule); font: 12px/1.3 var(--mono); }
.block div { padding: 10px 14px; border-right: 1px solid var(--rule); min-width: 0; }
.block div:last-child { border-right: 0; }
.block b { display: block; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 3px; }
.block .id { font: 700 22px/1 var(--display); color: var(--blue); display: flex; align-items: center; }
.body { padding: 26px 28px 30px; display: grid; gap: 22px; }
@media (max-width: 560px) { .body { padding: 20px 16px; } .block { grid-template-columns: 64px 1fr; } .block div:nth-child(3) { grid-column: 1 / -1; border-top: 1px solid var(--rule); } }
h2 { font: 700 clamp(26px, 3.2vw, 34px)/1.1 var(--display); margin: 0; text-wrap: balance; }
.q { font-size: 19px; line-height: 1.5; margin: 0; max-width: 64ch; }
h3 { font: 600 11px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; }
ul { margin: 0; padding-left: 20px; display: grid; gap: 6px; max-width: 68ch; }
.result { background: var(--wash); border-left: 3px solid var(--blue); padding: 14px 18px; font-size: 17px; font-variant-numeric: tabular-nums; }
.decision { border-left: 3px solid var(--ochre); padding: 4px 0 4px 18px; max-width: 68ch; }
figure { margin: 0; display: grid; gap: 8px; }
figure a { display: block; background: #fff; border: 1px solid var(--rule); border-radius: 2px; overflow: hidden; }
figure img { display: block; width: 100%; height: auto; }
figcaption { font-size: 14px; color: var(--muted); max-width: 72ch; }
figcaption span { font: 600 12px var(--mono); color: var(--ink); margin-right: 6px; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 22px; }
footer { grid-column: 1 / -1; font: 13px/1.5 var(--mono); color: var(--muted); border-top: 1px solid var(--rule); padding-top: 18px; }
@media (prefers-reduced-motion: no-preference) { nav.index a { transition: background .15s; } }
"""


def figure_html(eid, n, name, cap):
    src = f"../figures/{name}"          # the one figures folder (lab_book/figures), no copy beside the page
    return (f'<figure><a href="{src}" target="_blank" rel="noopener"><img src="{src}" alt="{html.escape(cap)}" loading="lazy"></a>'
            f'<figcaption><span>Fig. {eid}.{n}</span>{html.escape(cap)}</figcaption></figure>')


def entry(e, m):
    figs = [figure_html(e["id"], i + 1, f[0], f[1]) for i, f in enumerate(e["figures"]) if (BOOK / "figures" / f[0]).exists()]
    li = lambda xs: "<ul>" + "".join(f"<li>{fill(x, m)}</li>" for x in xs) + "</ul>"
    return f"""
<article class="sheet" id="{e['id'].lower()}">
  <div class="block"><div class="id">{e['id']}</div><div><b>Stage</b>{html.escape(e['stage'])}</div><div><b>Date</b>{e['date']}</div></div>
  <div class="body">
    <h2>{fill(e['title'], m)}</h2>
    <p class="q">{fill(e['question'], m)}</p>
    <div><h3>What we did</h3>{li(e['did'])}</div>
    {figs[0] if figs else ''}
    <div><h3>Result</h3><div class="result">{fill(e['result'], m)}</div></div>
    {('<div class="two">' + ''.join(figs[1:]) + '</div>') if len(figs) > 1 else ''}
    <div><h3>What we learned</h3>{li(e['learned'])}</div>
    <div><h3>Decision</h3><p class="decision">{fill(e['decision'], m)}</p></div>
  </div>
</article>"""


def main():
    data = json.load(open(BOOK / "experiments.json", encoding="utf-8"))
    ex, m = data["experiments"], metrics()
    SITE.mkdir(parents=True, exist_ok=True)
    used = [f[0] for e in ex for f in e["figures"]]
    nav = "".join(f'<a href="#{e["id"].lower()}"><span>{e["id"]}</span><span>{html.escape(e["title"])}</span></a>' for e in ex)
    page = f"""<title>NOMAD Lab Book</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=JetBrains+Mono:wght@400;600&family=Public+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
  <header class="book">
    <span class="eyebrow">IAAC · Master in AI for Architecture · Barcelona</span>
    <h1>NOMAD Lab Book</h1>
    <p class="lede">Every experiment on the way to NOMAD, the tool that checks whether a Barcelona shop or warehouse can legally become housing. Each sheet says what we asked, what we did, what came out, and what we decided. All numbers and charts come from our result files.</p>
    <div class="meta"><span>{len(ex)} experiments</span><span>{len([u for u in used if (BOOK / 'figures' / u).exists()])} figures</span><span>updated {date.today().isoformat()}</span><span>Bhavini · Alvaro · Bars</span></div>
  </header>
  <nav class="index" aria-label="Experiments"><div class="h">Sheets</div>{nav}</nav>
  <main>{''.join(entry(e, m) for e in ex)}</main>
  <footer>Built by lab_book/code/build_book.py from lab_book/experiments.json. Charts: lab_book/code/make_figures.py. Datasets: Swiss Dwellings v3.0.0 (CC BY 4.0), ResPlan (CC BY 4.0). Plan model: floorplan-to-3d (MIT).</footer>
</div>
"""
    (SITE / "index.html").write_text(page, encoding="utf-8")
    missing = sorted(set(__import__("re").findall(r"\{([a-z0-9_]+)\}", page)))
    print(f"book: {len(ex)} experiments, {len(used)} figures -> {SITE / 'index.html'}")
    if missing:
        print("  ! numbers not found:", missing)


if __name__ == "__main__":
    main()
