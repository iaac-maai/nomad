"""Nomad - draw the lab book's figures from our result files (nothing typed by hand).

Every chart reads a file in results/ or 7_floor_plans/output/clean/, so re-running this after an experiment
redraws the book with the new numbers. Pictures of plans are copied from where the experiment saved them.
Output: lab_book/figures/*.png   Run: .venv/Scripts/python lab_book/code/make_figures.py
"""
import csv, json, glob
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "lab_book/figures"
DASH = ROOT / "8_report_and_city/output/dashboard/dashboard_data"
INK, MUTED, GRID = "#1d2733", "#5f6b78", "#e3e6ea"
BLUE, OCHRE, GREEN, RED, VIOLET = "#2c5d8f", "#c98a2b", "#3f8f5a", "#c4473a", "#7a5aa6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "figure.dpi": 150})


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor="white")
    plt.close(fig)
    print("  ", name)


def rulebook():
    r = rows(DASH / "rulebook_norms.csv")
    r.sort(key=lambda x: int(x["pieces"]))
    lvl = {"national": BLUE, "catalonia": OCHRE, "pgm": GREEN, "barcelona": RED}
    fig, ax = plt.subplots(figsize=(8, 0.28 * len(r) + 1))
    ax.barh([x["norm"] for x in r], [int(x["pieces"]) for x in r], color=[lvl.get(x["level"].lower(), VIOLET) for x in r])
    ax.set_xlabel("pieces of law in the rulebook")
    ax.grid(axis="y", visible=False)
    for k, c in lvl.items():
        ax.bar(0, 0, color=c, label=k)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "e01_rulebook_pieces.png")


def rule_pass():
    r = rows(DASH / "rule_results.csv")
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(r) + 1))
    y = range(len(r))
    for i, (col, lab, c) in enumerate([("swiss_flats_pass", "Swiss flats", BLUE), ("swiss_shops_pass", "Swiss shops", OCHRE), ("resplan_pass", "ResPlan flats", GREEN)]):
        vals = [float(x[col]) if x[col] else 0 for x in r]
        ax.barh([j + (i - 1) * 0.27 for j in y], vals, height=0.26, color=c, label=lab)
    ax.set_yticks(list(y), [x["rule"] for x in r])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.set_xlabel("share of plans that pass")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower left", ncol=3, bbox_to_anchor=(0, 1))
    save(fig, "e02_rule_pass_rates.png")


def bedrooms():
    r = rows(DASH / "by_bedrooms.csv")
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.bar([x["bedrooms"] for x in r], [float(x["all_rules_pass"]) for x in r], color=BLUE)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.set_ylabel("pass all rules")
    ax.set_xlabel("bedrooms")
    ax.grid(axis="x", visible=False)
    save(fig, "e02_pass_by_bedrooms.png")


def cleaning():
    r = rows(ROOT / "7_floor_plans/output/clean/cleaning_report.csv")
    from collections import Counter
    c = Counter("kept" if x["kept"] == "True" else x["reason"] for x in r)
    labels = list(c)
    fig, ax = plt.subplots(figsize=(8, 2.6))
    ax.barh(labels, [c[k] for k in labels], color=[GREEN if k == "kept" else MUTED for k in labels])
    for i, k in enumerate(labels):
        ax.text(c[k] + 2, i, str(c[k]), va="center", color=INK)
    ax.invert_yaxis()
    ax.set_xlabel(f"Swiss commercial units (of {len(r)})")
    ax.grid(axis="y", visible=False)
    save(fig, "e03_dataset_cleaning.png")


def programs():
    p = json.load(open(ROOT / "7_floor_plans/output/generation/room_programs.json", encoding="utf-8"))["programs"]
    keys = [("living_m2", "living", OCHRE), ("main_bedroom_m2", "main bedroom", VIOLET), ("other_bedroom_m2", "other bedrooms", "#b3a3d6"),
            ("kitchen_m2", "kitchen", "#e7c27a"), ("bath_m2", "bath", "#86b3dd"), ("circulation_m2", "hall", "#c8ccd1")]
    names = list(p)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    left = [0] * len(names)
    for k, lab, c in keys:
        vals = []
        for n in names:
            v = p[n].get(k) or {}
            m = v.get("median", 0) if isinstance(v, dict) else 0
            if k == "other_bedroom_m2" and m:
                m *= max(0, p[n]["bedrooms"] - 1)
            vals.append(m)
        ax.barh(names, vals, left=left, color=c, label=lab)
        left = [a + b for a, b in zip(left, vals)]
    for i, n in enumerate(names):
        ax.text(left[i] + 1, i, f"{p[n]['useful_m2']['median']:.0f} m² useful · from {p[n]['flats_learned_from']:,} flats", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, max(left) * 1.6)
    ax.invert_yaxis()
    ax.set_xlabel("m² (typical size, median)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=6, fontsize=7, loc="lower left", bbox_to_anchor=(0, 1))
    save(fig, "e04_room_programs.png")


def generation():
    r = rows(DASH / "generation.csv")
    mixes = list(dict.fromkeys(x["mix"] for x in r))
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(mixes) + 1))
    for i, (size, c) in enumerate([("typical", BLUE), ("compact", OCHRE)]):
        vals = [next((float(x["share_of_180_shops"]) for x in r if x["mix"] == m and x["room_sizes"] == size), 0) for m in mixes]
        ax.barh([j + (i - 0.5) * 0.38 for j in range(len(mixes))], vals, height=0.36, color=c, label=f"{size} rooms")
    ax.set_yticks(range(len(mixes)), mixes)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.set_xlabel("share of the 180 shops where every flat fits and passes")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "e05_generation_by_mix.png")


def reader_eval():
    r = [x for x in rows(ROOT / "2_building/output/plan_reading/eval.csv") if x["ok"] == "True"]
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    for mode, c in (("scale given", BLUE), ("scale estimated", OCHRE)):
        axs[0].hist([float(x["iou"]) for x in r if x["mode"] == mode], bins=20, range=(0, 1), color=c, alpha=0.8, label=mode)
        axs[1].hist([min(1, float(x["area_err"])) for x in r if x["mode"] == mode], bins=20, range=(0, 1), color=c, alpha=0.8, label=mode)
    axs[0].set_xlabel("outline overlap (1 = perfect)")
    axs[1].set_xlabel("area error (0 = perfect)")
    axs[0].set_ylabel("plans")
    axs[0].legend(frameon=False, fontsize=8)
    save(fig, "e06_reader_accuracy.png")


def reader_compare():
    files = sorted(glob.glob(str(ROOT / "2_building/output/plan_reading/compare" / "*.json")))
    if not files:
        return
    names = {"f3d": "floorplan-to-3d\n+ dark lines (ours)", "f3d_only": "floorplan-to-3d\nmodel alone", "mitunet": "MitUNet walls\n+ dark lines", "dark": "dark lines\nalone (no AI)"}
    res = {}
    for f in files:
        plans, walls = Path(f).stem.split("__")
        res.setdefault(walls, {})[plans] = json.load(open(f))["scale given"]
    order = [w for w in names if w in res]
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, key, lab in ((axs[0], "median_iou", "median outline overlap"), (axs[1], "area_within_10pct", "plans with area within 10%")):
        for i, (plans, c, tl) in enumerate((("test_plans", BLUE, "clean plans"), ("test_plans_messy", OCHRE, "messy plans"))):
            vals = [res[w].get(plans, {}).get(key, 0) for w in order]
            ax.bar([j + (i - 0.5) * 0.38 for j in range(len(order))], vals, width=0.36, color=c, label=tl)
            for j, v in enumerate(vals):
                ax.text(j + (i - 0.5) * 0.38, v + 0.01, f"{v:.2f}" if key == "median_iou" else f"{v:.0%}", ha="center", fontsize=7, color=INK)
        ax.set_xticks(range(len(order)), [names[w] for w in order], fontsize=7)
        ax.set_ylim(0, 1.1)
        ax.set_title(lab, fontsize=10, color=INK)
        ax.grid(axis="x", visible=False)
    axs[0].legend(frameon=False, fontsize=8, loc="lower left")
    save(fig, "e07_reader_comparison.png")


def strip(paths, name, labels, h=420):
    ims = [Image.open(p).convert("RGB") for p in paths if Path(p).exists()]
    if not ims:
        return
    ims = [im.resize((max(1, int(im.width * h / im.height)), h)) for im in ims]
    W = sum(im.width for im in ims) + 20 * (len(ims) - 1)
    sheet = Image.new("RGB", (W, h + 34), "white")
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        f = ImageFont.load_default()
    x = 0
    for im, lab in zip(ims, labels):
        sheet.paste(im, (x, 34))
        d.text((x, 6), lab, fill=INK, font=f)
        x += im.width + 20
    sheet.save(OUT / name)
    print("  ", name)


def plan_pictures():
    tp, ms, pr = ROOT / "7_floor_plans/input/datasets/test_plans", ROOT / "7_floor_plans/input/datasets/test_plans_messy", ROOT / "2_building/output/plan_reading"
    strip([tp / "145057.png", ms / "145057.jpg", pr / "from_rhino/145057_read.png"], "e06_test_plan_clean_messy_read.png",
          ["1. clean test plan", "2. messy copy (text, dims, scan)", "3. what the reader found"])
    nice = {"f3d_only": "AI model alone", "dark": "dark lines alone", "f3d": "AI + dark lines (ours)", "mitunet": "MitUNet + dark lines"}
    strip([pr / "compare" / f"145057_read_{w}.png" for w in nice], "e07_readers_side_by_side.png", list(nice.values()))
    samples = sorted(glob.glob(str(ROOT / "7_floor_plans/input/datasets/floorplan_images_samples/*.png")))[:2]
    previews = [pr / (Path(s).stem + ".preview.png") for s in samples]
    strip([p for pair in zip(samples, previews) for p in pair], "e06_first_reading_test.png",
          ["plan image", "model's walls / doors", "plan image", "model's walls / doors"], h=360)
    gen = ROOT / "7_floor_plans/output/generation/sample_plans.png"
    if gen.exists():
        Image.open(gen).convert("RGB").save(OUT / "e05_generated_plans.png")
        print("   e05_generated_plans.png")


ROOMCOL = {"living": "#f09f26", "bed_main": "#8078de", "bed": "#b0a8ed", "kitchen": "#fac775", "bath": "#85b8eb", "hall": "#cccccc"}


def plans_3d():
    """3D views of generated proposals (extruded rooms on the shop outline), like Rhino's preview."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    data = json.load(open(ROOT / "7_floor_plans/output/generation/sample_plans.json", encoding="utf-8"))["samples"]
    picks = [d for d in data if d["plan"]["proposal_ok"]]
    picks = sorted(picks, key=lambda d: len(d["plan"]["units"]))
    mid = [d for d in picks if 2 <= len(d["plan"]["units"]) <= 6]
    picks = [picks[0], mid[len(mid) // 3], mid[-1]] if len(mid) > 2 else picks[:3]
    fig = plt.figure(figsize=(12, 4.4))
    for i, smp in enumerate(picks):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        s, plan, H = smp["shell"], smp["plan"], 2.8
        ol = s["outline"]
        ax.plot([p[0] for p in ol + ol[:1]], [p[1] for p in ol + ol[:1]], 0, color="#777", linewidth=0.8)  # shop outline
        for u in plan["units"]:
            for r in u["rooms"]:
                if len(r["pts"]) < 3:
                    continue
                h = 0.05 if r["kind"] == "hall" else H
                c = ROOMCOL.get(r["kind"], "#ccc") if r.get("ok", True) else RED
                pts = r["pts"]
                faces = [[(x, y, h) for x, y in pts]]
                faces += [[(pts[k][0], pts[k][1], 0), (pts[(k + 1) % len(pts)][0], pts[(k + 1) % len(pts)][1], 0),
                           (pts[(k + 1) % len(pts)][0], pts[(k + 1) % len(pts)][1], h), (pts[k][0], pts[k][1], h)] for k in range(len(pts))]
                ax.add_collection3d(Poly3DCollection(faces, facecolor=c, edgecolor="#444", linewidth=0.3, alpha=0.95))
        for a, b in s["facade"]:
            ax.plot([a[0], b[0]], [a[1], b[1]], [0.06, 0.06], color=BLUE, linewidth=2.5)
        xs, ys = [p[0] for p in ol], [p[1] for p in ol]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        dx, dy = max(xs) - min(xs), max(ys) - min(ys)
        ax.set_xlim(min(xs), max(xs)); ax.set_ylim(min(ys), max(ys)); ax.set_zlim(0, H)
        ax.set_box_aspect((dx, dy, H), zoom=1.25)
        ax.view_init(elev=32, azim=-60)
        ax.set_axis_off()
        n = len(plan["units"])
        ax.set_title(f"shop {s['shell_id']} · {s['area_m2']:.0f} m² · {n} flat{'s' if n > 1 else ''}", fontsize=9, color=INK)
    save(fig, "e05_generated_plans_3d.png")


def rhino_sheets():
    """Stage 5 sheets drawn by NOMAD.gh / make_sheets.py in Rhino, copied in (not redrawn here)."""
    sh = ROOT / "7_floor_plans/output/sheets/stage5_v1"
    for src, dst in (("shop_70_deep_2x1bed.png", "e08_sheet_deep_warehouse_NO.png"), ("test_plan_145057.png", "e08_sheet_read_plan_PARTLY.png"),
                     ("shop_5_2x1bed_1x2bed.png", "e08_sheet_shop_YES.png"), ("shop_178_deep_5x1bed_2x2bed.png", "e08_sheet_large_PARTLY.png")):
        if (sh / src).exists():
            Image.open(sh / src).convert("RGB").save(OUT / dst)
            print("  ", dst)


def stage6():
    """Rhino before / after sheets (copied in) and the before / after chart from 7_floor_plans/output/generation/stage6_summary.json."""
    sh = ROOT / "7_floor_plans/output/sheets"
    for src, dst in (("E09_shop_79_patio_2x1bed_1x2bed.png", "e09_patio_before_after.png"), ("E09_shop_154608_deep_2x1bed.png", "e09_narrow_NO.png"),
                     ("E09_test_plan_145057.png", "e09_plan_drawing.png"), ("E09_shop_146519_2x1bed_1x2bed.png", "e09_yes_no_change.png")):
        if (sh / src).exists():
            Image.open(sh / src).convert("RGB").save(OUT / dst)
            print("  ", dst)
    f = ROOT / "7_floor_plans/output/generation/stage6_summary.json"
    if not f.exists():
        return
    s6 = {k: v for k, v in json.load(open(f, encoding="utf-8")).items() if k != "rules"}
    names = list(s6)
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(names) + 1))
    for i, (key, c, lab) in enumerate((("passing_flats_v1", MUTED, "first generator"), ("passing_flats_after", BLUE, "Stage 6 (patios + corridor)"))):
        vals = [s6[n][key] for n in names]
        ax.barh([j + (i - 0.5) * 0.38 for j in range(len(names))], vals, height=0.36, color=c, label=lab)
        for j, v in enumerate(vals):
            ax.text(v + 3, j + (i - 0.5) * 0.38, str(v), va="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlabel("flats that pass every rule, over 180 shops")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "e09_before_after_chart.png")


def demo_boards():
    """E10: the demo boards drawn in Rhino (copied in) and a chart of homes per iteration."""
    sh = ROOT / "7_floor_plans/output/sheets"
    for src, dst in (("D0_plan_drawing_145057_board.png", "e10_board_plan_drawing.png"), ("D1_shop_146519_YES_board.png", "e10_board_yes.png"),
                     ("D2_warehouse_154822_patio_board.png", "e10_board_patio.png"), ("D3_large_shop_152418_board.png", "e10_board_large.png"),
                     ("D4_warehouse_154608_NO_board.png", "e10_board_no.png")):
        if (sh / src).exists():
            im = Image.open(sh / src).convert("RGB")
            im.thumbnail((2200, 2200))
            im.save(OUT / dst)
            print("  ", dst)
    f = ROOT / "7_floor_plans/output/generation/iterations_summary.json"
    if not f.exists():
        return
    it = json.load(open(f, encoding="utf-8"))["iterations"]
    names = list(it)
    fig, ax = plt.subplots(figsize=(7, 2.6))
    vals = [it[n]["homes"] for n in names]
    ax.barh(names, vals, color=[MUTED, OCHRE, BLUE])
    for j, v in enumerate(vals):
        ax.text(v + 4, j, "%d homes" % v, va="center", fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_xlabel("homes that pass every rule, over 180 shops (asked 2 x 1-bed + 1 x 2-bed)")
    ax.grid(axis="y", visible=False)
    save(fig, "e10_homes_chart.png")


VC = {"YES": "#3f8f5a", "PARTLY": "#c98a2b", "NO": "#c4473a"}


def _trim(im, pad=16):
    from PIL import ImageChops, ImageOps
    bb = ImageChops.difference(im, Image.new(im.mode, im.size, (255, 255, 255))).getbbox()
    return ImageOps.expand(im.crop(bb) if bb else im, border=pad, fill=(255, 255, 255))


def _font(size, bold=False):
    from PIL import ImageFont
    for n in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _row(items, out, h=520, gap=40, cap_h=86):
    """Pictures in a row, each with a caption under it: (path, title, verdict, detail). Verdict is part of the caption text."""
    from PIL import ImageDraw
    ims = [(_trim(Image.open(p).convert("RGB")), t, v, d) for p, t, v, d in items if Path(p).exists()]
    if not ims:
        return
    ims = [(im.resize((int(im.width * h / im.height), h)), t, v, d) for im, t, v, d in ims]
    W = sum(im.width for im, _, _, _ in ims) + gap * (len(ims) - 1)
    sheet = Image.new("RGB", (W, h + cap_h), "white")
    dr = ImageDraw.Draw(sheet)
    x = 0
    for im, t, v, d in ims:
        sheet.paste(im, (x, 0))
        dr.text((x, h + 10), t, fill=INK, font=_font(26, True))
        if v:
            dr.text((x, h + 46), v, fill=VC[v], font=_font(26, True))
            dr.text((x + dr.textlength(v + "  ", font=_font(26, True)), h + 46), d, fill=INK, font=_font(26))
        elif d:
            dr.text((x, h + 46), d, fill=INK, font=_font(26))
        x += im.width + gap
    sheet.save(OUT / out)
    print("  ", out)


def _case(name):
    p = ROOT / "7_floor_plans/output/sheets/recipes" / (name + ".json")
    return json.load(open(p, encoding="utf-8"))["case"] if p.exists() else None


def cases_v2():
    """E08-E10 figures redrawn from the saved Rhino results (7_floor_plans/output/figures, lab_book/code/draw_cases.py): E05 colours,
    light gradient, verdict in the caption."""
    F = ROOT / "7_floor_plans/output/figures"
    # E08: flags on the shop as it is
    items = []
    for n, t in (("D1_shop_146519_YES", "a shop that works"), ("D0_plan_drawing_145057", "a plan drawing"),
                 ("D2_warehouse_154822_patio", "a deep warehouse"), ("D4_warehouse_154608_NO", "a narrow warehouse")):
        c = _case(n)
        if c:
            r = c["before"]["res"]
            items.append((F / (n + "_p0_plan.png"), t, r["verdict"], "%d of %d flats pass" % (r["flats_passing"], r["flats_asked"])))
    _row(items, "e08_flags_as_it_is.png")
    # E09: before / after
    for n, out in (("E09_shop_79_patio_2x1bed_1x2bed", "e09_patio_before_after.png"), ("E09_shop_154608_deep_2x1bed", "e09_narrow_NO.png"),
                   ("E09_test_plan_145057", "e09_plan_drawing.png"), ("E09_shop_146519_2x1bed_1x2bed", "e09_yes_no_change.png")):
        c = _case(n)
        if c:
            b, a = c["before"]["res"], c["after"]["res"]
            _row([(F / (n + "_before_plan.png"), "before: as it is", b["verdict"], "%d of %d flats" % (b["flats_passing"], b["flats_asked"])),
                  (F / (n + "_after_plan.png"), "after: " + ("patio + corridor" if c["after"]["plan"].get("patios") else "no building work"),
                   a["verdict"], "%d of %d flats" % (a["flats_passing"], a["flats_asked"]))], out)
    # E10: the demo, per shop: as it is + 3 layouts, and the 3D of each layout
    for n, out in (("D0_plan_drawing_145057", "e10_board_plan_drawing.png"), ("D1_shop_146519_YES", "e10_board_yes.png"),
                   ("D2_warehouse_154822_patio", "e10_board_patio.png"), ("D3_large_shop_152418", "e10_board_large.png"),
                   ("D4_warehouse_154608_NO", "e10_board_no.png")):
        c = _case(n)
        if not c:
            continue
        r0 = c["before"]["res"]
        plans = [(F / (n + "_p0_plan.png"), "as it is", r0["verdict"], "%d of %d flats" % (r0["flats_passing"], r0["flats_asked"]))]
        for k, it in enumerate(c["iterations"]):
            plans.append((F / ("%s_p%d_plan.png" % (n, k + 1)), it["label"], it["res"]["verdict"],
                          "%d home%s%s" % (it["homes"], "" if it["homes"] == 1 else "s", " + patio" if it["plan"].get("patios") else "")))
        _row(plans, "_tmp_plans.png")
        _row([(F / ("%s_p%d_3d.png" % (n, k + 1)), "3D, layout %d" % (k + 1), None, "") for k in range(len(c["iterations"]))],
             "_tmp_3d.png", h=360, cap_h=50)
        a, b = Image.open(OUT / "_tmp_plans.png"), Image.open(OUT / "_tmp_3d.png")
        W = max(a.width, b.width)
        board = Image.new("RGB", (W, a.height + b.height + 40), "white")
        board.paste(a, (0, 0))
        board.paste(b, ((W - b.width) // 2, a.height + 40))
        board.save(OUT / out)
        print("  ", out)
    for t in ("_tmp_plans.png", "_tmp_3d.png"):
        if (OUT / t).exists():
            (OUT / t).unlink()


def walls_3d():
    """E11: Stage 7.1 zoning next to Stage 7.2 walls, doors and windows, both captured in Rhino (7_floor_plans/output/sheets)."""
    S = ROOT / "7_floor_plans/output/sheets"
    for n, out in (("D0_plan_drawing_145057", "e11_walls_plan_drawing.png"), ("D1_shop_146519_YES", "e11_walls_yes.png"),
                   ("D2_warehouse_154822_patio", "e11_walls_patio.png")):
        c = _case(n)
        if not c:
            continue
        k = len(c["iterations"])
        it = c["iterations"][-1]
        homes = "%d home%s" % (it["homes"], "" if it["homes"] == 1 else "s")
        _row([(S / ("%s_3d_%d.png" % (n, k)), "7.1 zoning: rooms as blocks", it["res"]["verdict"], homes),
              (S / ("%s_walls_%d.png" % (n, k)), "7.2 walls, doors, windows", it["res"]["verdict"], homes)], out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (rulebook, rule_pass, bedrooms, cleaning, programs, generation, plans_3d, reader_eval, reader_compare, plan_pictures, rhino_sheets, stage6, demo_boards, cases_v2, walls_3d):
        try:
            f()
        except Exception as e:  # one broken chart must not stop the book
            print("  !", f.__name__, e)


if __name__ == "__main__":
    main()
