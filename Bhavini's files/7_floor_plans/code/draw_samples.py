"""Draw generated plans (7_floor_plans/output/generation/sample_plans.json) as one PNG contact sheet, top view.
Grey outline = the shop; coloured rooms = the proposal; red room = fails a rule; thick blue = façade.
Output: 7_floor_plans/output/generation/sample_plans.png"""
import json, sys
import pymupdf

COL = {"living": (0.94, 0.62, 0.15), "bed_main": (0.50, 0.47, 0.87), "bed": (0.69, 0.66, 0.93),
       "kitchen": (0.98, 0.78, 0.46), "bath": (0.52, 0.72, 0.92), "hall": (0.80, 0.80, 0.80)}
RED = (0.89, 0.29, 0.29)


def main(n=12, cols=4, cell=300):
    data = json.load(open("7_floor_plans/output/generation/sample_plans.json", encoding="utf-8"))["samples"]
    picks = data[:: max(1, len(data) // n)][:n]
    rows = (len(picks) + cols - 1) // cols
    doc = pymupdf.open()
    page = doc.new_page(width=cols * cell, height=rows * (cell + 40))
    for i, smp in enumerate(picks):
        s, plan = smp["shell"], smp["plan"]
        ox, oy = (i % cols) * cell, (i // cols) * (cell + 40)
        xs = [p[0] for p in s["outline"]]
        ys = [p[1] for p in s["outline"]]
        k = (cell - 30) / max(max(xs) - min(xs), max(ys) - min(ys), 1)
        T = lambda p: pymupdf.Point(ox + 15 + (p[0] - min(xs)) * k, oy + 15 + (max(ys) - p[1]) * k)
        page.draw_polyline([T(p) for p in s["outline"]], color=(0.4, 0.4, 0.4), fill=(0.95, 0.95, 0.95), width=1)
        for a, b in s["facade"]:
            page.draw_line(T(a), T(b), color=(0.16, 0.47, 0.84), width=3)
        for u in plan["units"]:
            for r in u["rooms"]:
                if len(r["pts"]) >= 3:
                    page.draw_polyline([T(p) for p in r["pts"]] + [T(r["pts"][0])], color=(1, 1, 1), width=0.5,
                                       fill=COL.get(r["kind"], COL["hall"]) if r.get("ok", True) else RED)
        mix = ", ".join("%d x %s" % (v, t) for t, v in smp["mix"].items() if v)
        page.insert_text(pymupdf.Point(ox + 15, oy + cell + 12), "shop %d: %.0f m2, façade %.0f m" % (s["shell_id"], s["area_m2"], s["facade_m"]), fontsize=9)
        page.insert_text(pymupdf.Point(ox + 15, oy + cell + 26), "%s -> %d flats pass, %.0f m2 unused" % (mix, plan["compliant"], plan["unused_m2"]), fontsize=9)
    page.get_pixmap(dpi=110).save("7_floor_plans/output/generation/sample_plans.png")
    print("wrote 7_floor_plans/output/generation/sample_plans.png with", len(picks), "plans")


if __name__ == "__main__":
    main(*map(int, sys.argv[1:]))
