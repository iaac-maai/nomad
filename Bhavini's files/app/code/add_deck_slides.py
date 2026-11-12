"""Add Bhavini's NOMAD slides to the team deck, in its design language, one slide per stage (4 slides).

The team deck is never changed: it is copied and 4 slides are added on its framed "EXPERIMENTS V0" sheet, in
Courier New, with every chart and picture in the lab-book colour scheme (E01 charts, E05 plans and 3D).
Each slide reads like a lab-book entry: a picture or chart, two or three big numbers, and one row of four short
cards - what we did / result / what we learned / decision. Placed after Exp 2, before "Next".
Run: .venv/Scripts/python app/code/add_deck_slides.py <team.pptx> <out.pptx> <image folder>
"""
import csv, json, sys
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
INK, DARK, ACC, MUTED, PINK, PAPER, SLATE, LINE = "1F1F1F", "2B2B2B", "C0704F", "8C8A82", "F3DDD2", "FAF9F5", "4A4F55", "E4E1DA"
# lab-book colours (E01 / E05): levels of law, datasets, verdicts
BLUE, OCHRE, GREEN, RED = "2C5D8F", "C98A2B", "3F8F5A", "C4473A"
VCOL = {"YES": GREEN, "PARTLY": OCHRE, "NO": RED}
FONT = "Courier New"
TOP = 1.32                        # content starts under the title band of the framed sheet; cards end at 6.6 (footer at 6.78)


def rgb(h):
    return RGBColor.from_string(h)


class Slide:
    def __init__(self, prs, layout, title, notes):
        self.s = prs.slides.add_slide(layout)
        t = self.s.shapes.title
        t.text_frame.text = ""
        r = t.text_frame.paragraphs[0].add_run()
        r.text = title
        self._font(r, 22, INK, bold=True)
        self.s.notes_slide.notes_text_frame.text = notes

    @staticmethod
    def _font(run, size, color, bold=False, italic=False):
        f = run.font
        f.name, f.size, f.bold, f.italic = FONT, Pt(size), bold, italic
        f.color.rgb = rgb(color)

    def text(self, x, y, w, h, parts, size=11, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False):
        """parts: a string, or a list of lines; a line is a string or a list of (text, {size,color,bold}) runs."""
        tb = self.s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        lines = parts if isinstance(parts, list) else [parts]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            for txt, o in (line if isinstance(line, list) else [(line, {})]):
                r = p.add_run()
                r.text = txt
                self._font(r, o.get("size", size), o.get("color", color), o.get("bold", bold), o.get("italic", italic))
        return tb

    def fig(self, x, y, num, caption, w=6.0):
        return self.text(x, y, w, 0.2, [[("FIG.%d  " % num, {"bold": True}), (caption.upper(), {})]], size=9, color=MUTED)

    def box(self, x, y, w, h, fill=PAPER, line=INK, weight=0.75, shape=MSO_SHAPE.RECTANGLE):
        b = self.s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        b.shadow.inherit = False
        if fill:
            b.fill.solid()
            b.fill.fore_color.rgb = rgb(fill)
        else:
            b.fill.background()
        if line:
            b.line.color.rgb = rgb(line)
            b.line.width = Pt(weight)
        else:
            b.line.fill.background()
        return b

    def badge(self, x, y, n, d=0.32):
        c = self.box(x, y, d, d, fill=ACC, line=ACC, shape=MSO_SHAPE.OVAL)
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(n)
        self._font(r, 10.5, "FFFFFF", bold=True)
        return c

    def image(self, path, x, y, w, h, frame=False, alt=""):
        iw, ih = Image.open(path).size
        s = min(w / iw, h / ih)
        pw, ph = iw * s, ih * s
        pic = self.s.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
        pic.shadow.inherit = False
        if alt:
            pic._element.nvPicPr.cNvPr.set("descr", alt)
        if frame:
            pic.line.color.rgb = rgb(INK)
            pic.line.width = Pt(0.75)
        return pic

    def stat(self, x, y, w, big, label, color=ACC, size=34):
        self.text(x, y, w, 0.62, big, size=size, color=color, bold=True)
        self.text(x, y + 0.62, w, 0.5, label, size=9.5, color=SLATE)

    def chart(self, x, y, w, h, cats, series, colors, kind="bar", number_format='0', max_v=None, gap=60, legend=False,
              point_colors=False, font=9, label_font=9.5):
        cd = CategoryChartData()
        cd.categories = cats
        for name, vals in series:
            cd.add_series(name, vals)
        t = XL_CHART_TYPE.BAR_CLUSTERED if kind == "bar" else XL_CHART_TYPE.COLUMN_CLUSTERED
        gf = self.s.shapes.add_chart(t, Inches(x), Inches(y), Inches(w), Inches(h), cd)
        ch = gf.chart
        ch.font.name, ch.font.size = FONT, Pt(font)
        ch.font.color.rgb = rgb(INK)
        ch.has_title = False
        ch.has_legend = legend
        if legend:
            ch.legend.position = XL_LEGEND_POSITION.TOP
            ch.legend.include_in_layout = False
            ch.legend.font.size = Pt(8.5)
        plot = ch.plots[0]
        plot.gap_width = gap
        if len(series) > 1:
            plot.overlap = -10
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format, dl.number_format_is_linked = number_format, False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size, dl.font.bold, dl.font.name = Pt(label_font), True, FONT
        va = ch.value_axis
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = rgb(LINE)
        va.format.line.fill.background()
        va.tick_labels.font.size = Pt(8)
        va.tick_labels.font.color.rgb = rgb(MUTED)
        va.minimum_scale = 0
        if max_v:
            va.maximum_scale = max_v
        ca = ch.category_axis
        ca.format.line.color.rgb = rgb(INK)
        ca.tick_labels.font.size = Pt(font)
        ca.reverse_order = kind == "bar"
        for k, s in enumerate(plot.series):
            s.format.fill.solid()
            s.format.fill.fore_color.rgb = rgb(colors[k % len(colors)])
            s.invert_if_negative = False
        if point_colors:
            for i, pt in enumerate(plot.series[0].points):
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = rgb(colors[i])
        return gf

    def strip(self, did, result, learned, decision, y=5.45, h=1.1):
        """The lab-book row: four short cards across the bottom of the sheet (ends at 6.55, above the footer)."""
        x0, w, gx = 0.55, 2.95, 0.12
        for k, (head, body) in enumerate((("WHAT WE DID", did), ("RESULT", result), ("WHAT WE LEARNED", learned), ("DECISION", decision))):
            x = x0 + k * (w + gx)
            last = k == 3
            self.box(x, y, w, h, fill=PINK if last else PAPER, line=ACC if last else LINE, weight=1.0 if last else 0.75)
            self.text(x + 0.14, y + 0.1, w - 0.28, 0.22, head, size=8.5, color=ACC, bold=True)
            self.text(x + 0.14, y + 0.34, w - 0.28, h - 0.42, body, size=9.5, color=INK)


# ---------- slide 2 (the team's pipeline): show steps 6 + 7 as running and link our experiments ----------
def _copy_look(dst, src):
    """Give shape dst the fill and outline of shape src (keeps dst's position)."""
    import copy
    sp_d, sp_s = dst._element.spPr, src._element.spPr
    for ch in list(sp_d):
        if not ch.tag.endswith("}xfrm") and not ch.tag.endswith("}prstGeom"):
            sp_d.remove(ch)
    for ch in sp_s:
        if not ch.tag.endswith("}xfrm") and not ch.tag.endswith("}prstGeom"):
            sp_d.append(copy.deepcopy(ch))


def _copy_run(dst, src, text=None):
    """Give the first run of dst the formatting of the first run of src (and new text)."""
    import copy
    rd = dst.text_frame.paragraphs[0].runs[0]
    rs = src.text_frame.paragraphs[0].runs[0]
    rd._r.replace(rd._r.rPr, copy.deepcopy(rs._r.rPr))
    if text is not None:
        dst.text_frame.paragraphs[0].runs[0].text = text


def _set_text(shape, lines):
    """Replace a text box's text, keeping its first run's formatting; lines = [[(text, bold?, accent?)]]."""
    import copy
    from pptx.enum.dml import MSO_THEME_COLOR
    tf = shape.text_frame
    p0 = tf.paragraphs[0]._p
    rs = p0.findall(qn("a:r"))
    r0 = copy.deepcopy(rs[0])
    r1 = copy.deepcopy(rs[1]) if len(rs) > 1 else r0   # plain (dark) run of a "label: text" callout
    template = copy.deepcopy(p0)
    for r in template.findall(qn("a:r")) + template.findall(qn("a:br")):
        template.remove(r)
    body = tf._txBody
    for para in body.findall(qn("a:p")):
        body.remove(para)
    for runs in lines:
        para = copy.deepcopy(template)
        end = para.find(qn("a:endParaRPr"))
        for txt, bold, accent in runs:
            r = copy.deepcopy(r1 if (bold is False and not accent) else r0)
            r.find(qn("a:t")).text = txt
            if end is not None:
                end.addprevious(r)
            else:
                para.append(r)
        body.append(para)
    for para, runs in zip(tf.paragraphs, lines):
        for run, (txt, bold, accent) in zip(para.runs, runs):
            if accent:
                run.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1


def _clone(slide, shape, x, y, w=None, h=None):
    import copy
    el = copy.deepcopy(shape._element)
    slide.shapes._spTree.append(el)
    new = slide.shapes[-1]
    new_id = max(sh.shape_id for sh in slide.shapes) + 1
    el.xpath("./*[1]/p:cNvPr")[0].set("id", str(new_id))
    new.left, new.top = Inches(x), Inches(y)
    if w is not None:
        new.width = Inches(w)
    if h is not None:
        new.height = Inches(h)
    return new


STEPS = [  # (name, what it uses) - the workflow, as on slide 2; ids = card, badge, number, name, text, tag (team slide)
    ((67, 68, 69, 70, 71, 72), None, None),
    ((74, 75, 76, 77, 78, 79), None, [[("Catastro + AI plan reader", None, False)]]),
    ((81, 82, 83, 84, 85, 86), None, [[("PGM zone of every empty shop (MUC, Generalitat)", None, False)]]),
    ((88, 89, 90, 91, 92, 93), None, [[("Decret 141/2012 -> AI rule cards, one rulebook", None, False)]]),
    ((95, 96, 97, 98, 99, 100), None, None),
    ((102, 103, 104, 105, 106, 107), "Check the shop", [[("every rule with its article -> YES / PARTLY / NO", None, False)]]),
    ((109, 110, 111, 112, 113, 114), "Fit the homes", [[("3 layouts, re-checked; 3D: zoning, then walls", None, False)]]),
    (None, "Report", [[("homes counted, smallest change, one sheet", None, False)]]),
]
PITCH, CARD_W, X0 = 1.537, 1.36, 0.60
LINES = (73, 80, 87, 94, 101, 108)


def _ctr(k):
    return X0 + k * PITCH + CARD_W / 2.0


def update_pipeline_slide(prs):
    """Slide 2, the team's pipeline, in workflow order: 8 steps (a 'check the shop' step before the homes are
    fitted; the report last, as it gathers everything), the experiments numbered in step order, slide pointers."""
    s = prs.slides[1]
    sh = dict((x.shape_id, x) for x in s.shapes)
    for run in sh[65].text_frame.paragraphs[0].runs:
        run.text = run.text.replace("7 steps", "8 steps")
    # step 8 = a copy of step 7's shapes; one more arrow
    keep = lambda i: (sh[i].left / 914400.0, sh[i].top / 914400.0)
    ids8 = [_clone(s, sh[i], *keep(i)).shape_id for i in STEPS[6][0]]
    _clone(s, sh[108], *keep(108))
    sh = dict((x.shape_id, x) for x in s.shapes)
    steps = [st[0] if st[0] else tuple(ids8) for st in STEPS]
    lines = list(LINES) + [max(sh) ]
    for k, (ids, (_, name, txt)) in enumerate(zip(steps, STEPS)):
        card, badge, num, nm, tx, tag = [sh[i] for i in ids]
        x = X0 + k * PITCH
        card.left, card.width = Inches(x), Inches(CARD_W)
        for el in (badge, num):
            el.left = Inches(x + 0.12)
        for el in (nm, tx, tag):
            el.left, el.width = Inches(x + 0.12), Inches(CARD_W - 0.20)
        if k >= 5 or k == 2:                           # steps 3 and 6-8 run (look of step 4)
            _copy_look(card, sh[88])
            _copy_look(badge, sh[89])
            _copy_run(num, sh[90], str(k + 1))
            _copy_run(tag, sh[93], "[ RUNNING ]")
        if name:
            nm.text_frame.paragraphs[0].runs[0].text = name
        if txt:
            _set_text(tx, txt)
        if k < 7:
            ln = sh[lines[k]]
            ln.left, ln.width = Inches(x + CARD_W + 0.02), Inches(PITCH - CARD_W - 0.04)
    # callouts: one box per experiment group, a line up to each step it tests
    B = 5.12
    box1 = _clone(s, sh[117], 0.60, B, 3.20, 1.45)
    t1 = _clone(s, sh[118], 0.74, B + 0.08, 2.92, 1.30)
    _set_text(t1, [[("EXP 1 (step 2): ", True, True), ("can AI read a shop from its plan drawing? (slide 3)", False, False)],
                   [("EXP 2 (step 3): ", True, True), ("can each empty shop take housing at all? (slide 4)", False, False)]])
    sh[117].left, sh[117].width = Inches(4.05), Inches(4.10)          # the team's box: rules + daylight
    sh[118].left, sh[118].width = Inches(4.19), Inches(3.82)
    paras = sh[118].text_frame.paragraphs
    for para, (old, new, ref) in zip(paras, (("EXP 2", "EXP 3", " (slides 5 to 7)"), ("EXP 1", "EXP 4", " (slides 8 to 11)"))):
        para.runs[0].text = para.runs[0].text.replace(old, new)
        para.runs[-1].text = para.runs[-1].text.rstrip() + ref
    box4 = _clone(s, sh[117], 8.45, B, 4.30, 1.45)
    t4 = _clone(s, sh[118], 8.59, B + 0.08, 4.02, 1.30)
    _set_text(t4, [[("EXP 5 (steps 6-8): ", True, True), ("can NOMAD check a shop, fit legal homes and build them in 3D?", False, False)],
                   [("(slides 12 to 13)", False, False)]])
    sh[115].left, sh[116].left = Inches(_ctr(3)), Inches(_ctr(4))
    for k in (1, 2, 5, 6, 7):
        _clone(s, sh[115], _ctr(k), 4.69)
    # bottom row: one line for the sentence + legend, one for the data
    sh[119].left, sh[119].top, sh[119].width, sh[119].height = Inches(0.60), Inches(6.70), Inches(7.0), Inches(0.3)
    runs = sh[119].text_frame.paragraphs[0].runs
    runs[0].text = "Each experiment is tested against a simple method or on real data."
    for r in runs[1:]:
        r.text = ""
    for r in runs:
        r.font.size = Pt(9.5)
    for sid, x in ((120, 7.75), (121, 8.13)):
        sh[sid].left, sh[sid].top = Inches(x), Inches(6.73 if sid == 120 else 6.74)
    sh[120].width = sh[120].height = Inches(0.22)
    sh[121].width = Inches(2.6)
    for sid in (122, 123):                                 # every step now runs: no "planned" key
        sh[sid]._element.getparent().remove(sh[sid]._element)
    runs = sh[124].text_frame.paragraphs[0].runs
    runs[-1].text = runs[-1].text.rstrip() + ", MUC zoning (Generalitat), census of ground-floor premises 2024 (Ajuntament)"
    sh[124].left, sh[124].top, sh[124].width, sh[124].height = Inches(0.60), Inches(7.02), Inches(12.1), Inches(0.25)
    s.notes_slide.notes_text_frame.text = (
        "Nomad answers one question for an empty ground-floor shop in Barcelona: can it become homes, how many, and what is the "
        "smallest change that makes it legal. The pipeline has eight steps. One, find the empty shops in the city census. Two, read "
        "the building, from the Catastro or from a plan drawing. Three, check the zoning: can this shop take housing at all. Four, extract the "
        "rules into one rulebook. Five, predict daylight. Six, check the shop as it is: every rule with its article, and a yes, "
        "partly or no. Seven, fit the homes: three layouts, each checked again, then built in 3D, first as zoning and then with "
        "walls, doors and windows. Eight, the report, which gathers all of it. Five experiments test the steps in this order: the "
        "plan reader, the zoning, the rules, daylight, and the check with the layouts. Each one is tested against a simple method or on real data.")


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(team, out, img):
    img = Path(img)
    prs = Presentation(team)
    update_pipeline_slide(prs)
    layout = [l for m in prs.slide_masters for l in m.slide_layouts
              if str(l.part.partname).endswith("slideLayout5.xml")][0]   # the framed "EXPERIMENTS V0" sheet (as Exp 1)
    dash = ROOT / "8_report_and_city/output/dashboard/dashboard_data"
    head = {r["metric"]: float(r["value"]) for r in rows(dash / "headline.csv")}
    levels = {}
    for r in rows(dash / "rulebook_norms.csv"):
        levels[r["level"]] = levels.get(r["level"], 0) + int(r["pieces"])
    rules = rows(dash / "rule_results.csv")
    ev = json.load(open(ROOT / "2_building/output/plan_reading/eval_summary.json"))["scale given"]
    race = {}
    for f in (ROOT / "2_building/output/plan_reading/compare").glob("test_plans_messy__*.json"):
        race[f.stem.split("__")[1]] = json.load(open(f))["scale given"]["area_within_10pct"]
    it = json.load(open(ROOT / "7_floor_plans/output/generation/iterations_summary.json", encoding="utf-8"))
    v5, its = it["stage5_flags_as_it_is"], it["iterations"]
    n_shops = sum(v5.values())
    h1, h2, h3 = its["1 as asked"]["homes"], its["2 as asked, compact rooms"]["homes"], its["3 most homes"]["homes"]
    any3 = its["3 most homes"]["shops_with_at_least_one_home"]
    vy, vp, vn = v5.get("YES", 0), v5.get("PARTLY", 0), v5.get("NO", 0)
    zon = json.load(open(ROOT / "1_find_the_shops/output/zoning/summary.json", encoding="utf-8"))

    # ---------- 1. Steps 4 + 9: the rulebook, tested on real flats (E01 + E02) ----------
    A = Slide(prs, layout, "Exp 3: one rulebook, tested on 46,937 real flats",
              "First we collected the law. National laws from the BOE, the building code CTE, the Catalan laws, and the Barcelona and "
              "metropolitan plans went into one rulebook of 2,470 pieces, each with its law and article. From it we wrote 9 rules for a "
              "new home and tested them on 46,937 real Swiss flats and 11,542 ResPlan plans. Swiss flats were not built for Catalan "
              "rules, so the point is which rule fails: the facade rule fails most. 97 of 341 shops pass the rules an empty shell can "
              "meet. Decision: every later step uses this one rulebook, and a layout counts as working only when all 9 rules pass.")
    A.fig(0.55, TOP, 1, "pieces of law in the rulebook, by level", w=4.2)
    lv = [("national", "Spain", BLUE), ("catalonia", "Catalonia", OCHRE), ("pgm", "Metropolitan", GREEN), ("barcelona", "Barcelona", RED)]
    A.chart(0.45, TOP + 0.2, 4.1, 2.35, [n for _, n, _ in lv], [("pieces", [levels.get(k, 0) for k, _, _ in lv])], [c for _, _, c in lv],
            point_colors=True, max_v=1400, gap=45)
    A.stat(0.55, TOP + 2.7, 2.0, "{:,}".format(int(head["rulebook_pieces"])), "pieces of law,\none file")
    A.stat(2.6, TOP + 2.7, 1.9, "%d" % head["norms"], "norms, each piece\nwith its article", color=INK)
    A.fig(4.85, TOP, 2, "share of real plans that pass each rule (%)", w=5.6)
    short = ["Area >= 36 m2", "Area >= 40 m2 (BCN)", "Bedroom >= 6 m2", "Bedroom 2 m square", "Living 2.8 m circle",
             "Windows >= 1/8", "Height >= 2.50 m", "Bathrooms", "Facade S/9 + 3 m"]
    vals = lambda k: [round(100 * float(r[k])) if r[k] else 0 for r in rules]
    A.chart(4.75, TOP + 0.15, 5.6, 3.85, short, [("Swiss flats", vals("swiss_flats_pass")), ("Swiss shops", vals("swiss_shops_pass")),
            ("ResPlan flats", vals("resplan_pass"))], [BLUE, OCHRE, GREEN], max_v=115, gap=55, legend=True, number_format='0;;;',
            font=8, label_font=7)
    A.stat(10.6, TOP + 0.3, 2.3, "%d %%" % round(100 * head["flats_all_pass"]), "of real flats pass\nall 9 rules")
    A.stat(10.6, TOP + 1.6, 2.3, "39 %", "pass the facade rule:\nthe one that fails most", color=RED)
    A.stat(10.6, TOP + 2.9, 2.3, "%d" % head["shops_convertible"], "of 341 shops pass the\nempty-shell rules", color=INK)
    A.strip("BOE, CTE, Catalan laws, PGM + Barcelona plans into one file; 9 rules coded with their articles.",
            "2,470 pieces from 22 norms. 32 % of 46,937 real flats pass all 9 rules.",
            "The facade rule decides most cases. Clean-up must never delete words like \"no\".",
            "One rulebook for every step. A layout works only when all 9 rules pass.")

    # ---------- 2. Step 2: read a shop's plan drawing (E06 + E07) ----------
    B = Slide(prs, layout, "Exp 1 (step 2): NOMAD reads a shop from its plan",
              "Next, NOMAD reads a floor plan drawing. An AI model from GitHub, floorplan-to-3d, labels walls, doors and windows; NOMAD "
              "then finds the outline of the shop and the street facade. We tested it on 180 shops drawn as plans with known answers, "
              "plus messy copies with text, dimension lines and scan noise. With one known size, the outline overlaps the truth 0.93 out "
              "of 1, and the area is within 10 percent on 77 percent of plans. Without a size the scale is a guess, about 50 percent off. "
              "We also raced four wall readers, including MitUNet from GitHub; it did not beat ours, so we kept ours. Decision: NOMAD "
              "always asks for one dimension.")
    B.fig(0.55, TOP, 1, "a test plan, a messy copy, and what NOMAD found")
    B.box(0.55, TOP + 0.22, 7.55, 3.6, fill="FFFFFF", line=INK)
    B.image(img / "read3.png", 0.65, TOP + 0.3, 7.35, 3.44, alt="clean plan, messy plan, outline found")
    B.text(0.55, TOP + 3.88, 7.55, 0.22, [[("red", {"color": RED, "bold": True}), (" = outline found     ", {}),
                                           ("green", {"color": GREEN, "bold": True}), (" = street facade found", {})]], size=9)
    B.stat(8.45, TOP, 2.1, "%.2f" % ev["median_iou"], "outline overlap\n(1 = perfect)")
    B.stat(10.65, TOP, 2.2, "%d %%" % round(100 * ev["area_within_10pct"]), "of 180 plans: area\nwithin 10 %")
    B.fig(8.45, TOP + 1.32, 2, "4 wall readers raced, 60 messy plans", w=4.4)
    names = [("f3d", "ours (AI + lines)", BLUE), ("dark", "dark lines only", MUTED), ("f3d_only", "AI model only", MUTED),
             ("mitunet", "MitUNet (GitHub)", OCHRE)]
    B.chart(8.35, TOP + 1.5, 4.5, 2.5, [n for _, n, _ in names], [("area within 10 %", [round(100 * race.get(k, 0)) for k, _, _ in names])],
            [c for _, _, c in names], point_colors=True, number_format='0"%"', max_v=100, gap=45)
    B.strip("AI model (GitHub, MIT) labels walls; NOMAD finds outline + facade. 180 test plans, clean and messy.",
            "Overlap 0.93; area within 10 % on 77 % of plans, when one size is given.",
            "Guessing the scale is ~50 % off. MitUNet was not better on our drawings.",
            "NOMAD always asks for one size (the street facade). Next: real scans.")

    # ---------- 2b. Exp 2, step 3: zoning of every empty shop in Barcelona (E12) ----------
    zh = zon["housing"]
    Z = Slide(prs, layout, "Exp 2 (step 3): can each empty shop become housing at all?",
              "Step 3 asks the first legal question: does the zoning allow housing here at all? We took the %s empty ground-floor "
              "premises of the city's 2024 census and the %s zoning polygons of the Mapa Urbanistic de Catalunya, and matched every "
              "shop door to the zone it stands in. The PGM, article 225.7, admits housing on the ground floor in the zones built "
              "along street lines: the old town, the Eixample and similar. %s premises, 82 percent, pass this first gate; %s depend "
              "on their zone's own plan, such as 22@ or specific volumetry; %s cannot take housing at all: facilities, parks, "
              "industry. In the Eixample it is 95 percent. So zoning is rarely the problem in the dense city: the rules inside "
              "the shop decide." % ("{:,}".format(zon["empty_premises"]), "{:,}".format(zon["zone_polygons"]),
                                     "{:,}".format(zh.get("YES", 0)), zh.get("CHECK", 0), zh.get("NO", 0)))
    Z.fig(0.55, TOP, 1, "empty shops, by what the zone allows", w=3.4)
    Z.box(0.55, TOP + 0.22, 3.3, 3.75, fill="FFFFFF", line=LINE)
    Z.image(img / "e12_zoning_map.png", 0.6, TOP + 0.27, 3.2, 3.65, alt="map of Barcelona's empty premises by zoning answer")
    Z.fig(4.2, TOP, 2, "empty premises by zone (PGM key)", w=4.6)
    kk = [("13a", "13a Eixample type"), ("12", "12 old town"), ("13b", "13b semi-intensive"), ("15", "15 conservation")]
    Z.chart(4.1, TOP + 0.18, 4.6, 2.6, [l for _, l in kk] + ["check the zone's plan", "not admitted"],
            [("premises", [zon["by_key"].get(k, 0) for k, _ in kk] + [zh.get("CHECK", 0), zh.get("NO", 0)])],
            [GREEN, GREEN, GREEN, GREEN, OCHRE, RED], point_colors=True, max_v=2900, gap=40)
    Z.text(4.2, TOP + 2.9, 4.5, 0.9, [[("Rule: ", {"bold": True}), ("PGM art. 225.7 (MPGM 1999) admits housing on the ground floor in "
                                                                     "zones built along street lines.", {})],
                                       [("Zones: ", {"bold": True}), ("MUC, Generalitat. Shops: census 2024, Ajuntament.", {})]],
           size=9, color=SLATE)
    ez = zon["eixample"]
    Z.stat(9.1, TOP + 0.1, 3.6, "%d %%" % round(100.0 * zh.get("YES", 0) / zon["empty_premises"]),
           "of %s empty premises: housing\nadmitted by the zone" % "{:,}".format(zon["empty_premises"]), color=GREEN)
    Z.stat(9.1, TOP + 1.45, 3.6, "%d %%" % round(100.0 * ez["housing"].get("YES", 0) / ez["empty"]),
           "in the Eixample (%s of %s)" % ("{:,}".format(ez["housing"].get("YES", 0)), "{:,}".format(ez["empty"])), color=INK)
    Z.stat(9.1, TOP + 2.8, 3.6, "%d" % zh.get("NO", 0), "cannot take housing:\nfacilities, parks, industry", color=RED)
    Z.strip("Matched %s empty shops (census 2024) to their zone (MUC, Generalitat), point in polygon." % "{:,}".format(zon["empty_premises"]),
            "%s pass (82 %%); %d depend on their zone's plan; %d cannot take housing." % ("{:,}".format(zh.get("YES", 0)), zh.get("CHECK", 0), zh.get("NO", 0)),
            "Zoning is rarely the problem in the dense city: the rules inside the shop decide.",
            "Zoning is NOMAD's first gate: type an address in NOMAD.gh. Next: the inner-block rule of art. 225.7.")

    # ---------- 3. Exp 5, step 6: check the shop as it is (E08), in one Grasshopper file ----------
    C = Slide(prs, layout, "Exp 5 (step 6): every shop checked: yes, partly or no",
              "Exp 5 tests steps 6 to 8, and all of it runs in one Grasshopper file, NOMAD.gh, inside Rhino. One: the shop, from a "
              "plan file, a traced outline or the dataset. Two: the flats asked for. Three: the NOMAD component. Four: switches to make "
              "a sheet, run a folder of plans, keep every experiment in the Rhino file, or make the demo. Five: the preview and the "
              "report. Step 6 checks the shop as it is: every rule with its article, flat by flat, and a verdict, yes, partly or no. "
              "The verdict is written under the plan, never on it. Over %d shops asking for two one-bedroom flats and one "
              "two-bedroom flat: %d yes, %d partly, %d no. Most partly shops are short of street facade, not of the rules. "
              "A shop conversion needs 2.40 metres of clear height, not 2.50 (Decret 141, Annex 4 group C)." % (n_shops, vy, vp, vn))
    C.fig(0.55, TOP, 1, "NOMAD.gh: the working Grasshopper definition", w=7)
    C.box(0.55, TOP + 0.22, 6.9, 3.3, fill="FFFFFF", line=INK)
    C.image(img / "nomad_gh.png", 0.62, TOP + 0.28, 6.76, 3.18, alt="NOMAD Grasshopper definition with its five groups")
    for k, t in enumerate(["The shop", "Flats asked", "NOMAD", "Make", "Report"]):
        x = 0.55 + k * 1.4
        C.badge(x, TOP + 3.62, k + 1, d=0.28)
        C.text(x + 0.34, TOP + 3.65, 1.02, 0.25, t, size=8.5)
    C.fig(7.75, TOP, 2, "flags on the shop as it is (Rhino)", w=5)
    C.box(7.75, TOP + 0.22, 5.1, 1.85, fill="FFFFFF", line=LINE)
    C.image(img / "e08_flags_as_it_is.png", 7.82, TOP + 0.28, 4.96, 1.73, alt="four shops as they are, with their verdicts")
    C.fig(7.75, TOP + 2.3, 3, "all %d shops, as they are" % n_shops, w=5)
    C.chart(7.65, TOP + 2.45, 3.3, 1.6, ["YES", "PARTLY", "NO"], [("shops", [v5.get("YES", 0), v5.get("PARTLY", 0), v5.get("NO", 0)])],
            [GREEN, OCHRE, RED], point_colors=True, max_v=120, gap=45)
    C.stat(11.05, TOP + 2.55, 1.9, "9", "rules, each with\nits article", color=INK, size=26)
    C.strip("Each shop checked as it is, flat by flat: 9 rules, each naming its article. One Grasshopper file.",
            "%d YES, %d PARTLY, %d NO over %d shops (2 x 1-bed + 1 x 2-bed asked)." % (vy, vp, vn, n_shops),
            "Most PARTLY shops lack street facade, not rules. Conversions need 2.40 m, not 2.50 m (Exp 3).",
            "Verdict in the caption, never on the plan. Then fit the homes (step 7).")

    # ---------- 4. Exp 4, steps 7-8: three layouts, 3D (zoning, then walls), the report (E03-E05, E10, E11) ----------
    D = Slide(prs, layout, "Exp 5 (steps 7-8): three layouts, built in 3D",
              "Step 7 fits the homes. Room sizes are learned from 13,444 real flats that pass all our rules. For each shop NOMAD draws "
              "three layouts and checks each one again. One: the flats asked for. Two: the same with compact room sizes, still legal. "
              "Three: as many homes as fit. Rooms that need daylight sit on the street facade, the blue line; kitchen and bath behind. "
              "This large shop holds 7 homes as asked and 12 at most. Over all %d shops: %d, %d and %d homes. Then each layout is "
              "built in Rhino in two steps: first the zoning, each room a coloured block, then the walls, with a door from every room "
              "to the hall and windows 1.5 m tall in the street facade. Step 8, the report, puts the plans, the 3D and the verdict on "
              "one sheet, and every one is kept in NOMAD.3dm, and exported as IFC and glTF." % (n_shops, h1, h2, h3))
    D.fig(0.55, TOP, 1, "one shop (850 m2): as it is, and three layouts", w=7)
    heads = [("As it is", "YES", "7 of 7 flats"), ("1  As asked", "YES", "7 homes"), ("2  Compact", "YES", "7 homes"),
             ("3  Most homes", "YES", "12 homes")]
    pw = 1.65
    for k, (h, v, n) in enumerate(heads):
        x = 0.55 + k * (pw + 0.1)
        D.image(img / ("v2_d3_p%d.png" % k), x, TOP + 0.25, pw, 2.6, alt=h)
        D.text(x, TOP + 2.92, pw, 0.22, h, size=9, bold=True, color=SLATE)
        D.text(x, TOP + 3.15, pw, 0.3, [[(v, {"color": VCOL[v], "bold": True}), ("  " + n, {"bold": k == 3})]], size=10)
    leg = [("living", "F09F26"), ("bedroom", "8078DE"), ("kitchen", "FAC775"), ("bath", "85B8EB"), ("street facade", BLUE)]
    for k, (n, col) in enumerate(leg):
        x = 0.55 + k * 1.3
        D.box(x, TOP + 3.62, 0.16, 0.14, fill=col, line=None)
        D.text(x + 0.22, TOP + 3.58, 1.05, 0.2, n, size=8.5, color=SLATE)
    D.fig(7.75, TOP, 2, "3D in Rhino: zoning, then walls, doors, windows", w=5)
    shots = [("rh_D0_plan_drawing_145057_3d_3.png", "zoning"), ("rh_D0_plan_drawing_145057_walls_3.png", "walls + openings"),
             ("rh_D1_shop_146519_YES_walls_3.png", "four homes")]
    for k, (f, cap) in enumerate(shots):
        x = 7.75 + k * 1.72
        D.box(x, TOP + 0.24, 1.62, 1.3, fill="FFFFFF", line=LINE)
        D.image(img / f, x + 0.06, TOP + 0.3, 1.5, 1.18, alt=cap)
        D.text(x, TOP + 1.6, 1.62, 0.22, cap, size=8.5, color=SLATE, align=PP_ALIGN.CENTER)
    D.text(9.30, TOP + 0.78, 0.2, 0.25, "->", size=9, color=SLATE, align=PP_ALIGN.CENTER)
    D.fig(7.75, TOP + 2.15, 3, "homes over all %d shops" % n_shops, w=5)
    D.chart(7.65, TOP + 2.3, 3.3, 1.75, ["1 as asked", "2 compact", "3 most homes"],
            [("homes", [h1, h2, h3])], [MUTED, SLATE, ACC], point_colors=True, max_v=int(h3 * 1.25), gap=40)
    D.stat(11.05, TOP + 2.45, 1.9, "%d/%d" % (any3, n_shops), "shops hold at\nleast one home", size=24)
    D.strip("3 layouts per shop, each re-checked; rooms from 13,444 real flats. 3D: zoning, then walls, doors, windows.",
            "%d / %d / %d homes over %d shops; %d shops hold at least one." % (h1, h2, h3, n_shops, any3),
            "'As many as fit' adds the most homes. Street facade, not the rules, is the limit.",
            "Report: plans + 3D + verdict on one sheet, in NOMAD.3dm + IFC. Next: Exp 4 daylight for the 5.5 m rule.")

    # ---------- the team's experiment slides, numbered in workflow order (daylight = Exp 3) ----------
    def retitle(slide, old, new_):
        for shp in slide.shapes:
            for sub in (shp.shapes if shp.shape_type == 6 else [shp]):
                if sub.has_text_frame:
                    for para in sub.text_frame.paragraphs:
                        for r in para.runs:
                            if old in r.text:
                                r.text = r.text.replace(old, new_)
    sl = list(prs.slides)
    retitle(sl[2], "Exp 1: AI predicts shop daylight better than the rule", "Exp 4 (step 5): AI predicts daylight better than the rule")
    retitle(sl[3], "Exp 1: ", "Exp 4: ")
    retitle(sl[4], "Exp 1 on real data", "Exp 4 on real data")
    retitle(sl[4], "Exp 1 model", "Exp 4 model")
    retitle(sl[5], "Real shops: how we measure them from open data", "Exp 4: how we measure real shops from open data")
    retitle(sl[6], "Exp 2: ", "Exp 3 (step 4): ")
    retitle(sl[7], "Exp 2: ", "Exp 3: ")
    retitle(sl[6], "rule accuracy from 46 % to 76 %", "rule accuracy 46 % -> 76 %")

    # ---------- deck in workflow order ----------
    # built: 0 title, 1 pipeline, 2-5 Exp 4 daylight, 6-7 Exp 3 rules, 8 next, 9 rulebook (A), 10 reader (B), 11 zoning (Z),
    # 12 check (C), 13 homes (D)
    lst = prs.slides._sldIdLst
    ids = list(lst)
    order = [0, 1, 10, 11, 6, 7, 9, 2, 3, 4, 5, 12, 13, 8]
    for e in ids:
        lst.remove(e)
    for i in order:
        lst.append(ids[i])
    prs.save(out)
    print("saved", out, "slides:", len(prs.slides))


if __name__ == "__main__":
    main(*sys.argv[1:4])
