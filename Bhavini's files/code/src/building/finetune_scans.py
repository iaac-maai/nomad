"""Nomad - Exp 1 next step: fine-tune the wall model (floorplan-to-3d, MIT; ResNet34-UNet, segmentation-models-pytorch)
on REAL SCANS instead of the clean SVG drawings it was trained on.

Data: CubiCasa5K (CC BY-NC-SA 4.0). Only the train and val splits are used, so the 398 test plans we score on stay
unseen. The files are read straight out of the Zenodo zip with HTTP range requests (remotezip), so the 5.47 GB zip is
never downloaded again: for each plan only F1_scaled.png (the scan, in the SVG's coordinates) and model.svg (the answer).
Labels: the plan's own SVG painted as floor / wall / door / window (floorplan-to-3d's svg_to_mask, MIT).
Training: start from the published weights; 512 px letterbox like inference; light paper augmentations (brightness,
contrast, blur, a colour shift for coloured plans); AdamW lr 2e-4; mixed precision on the GPU.
Run (GPU environment):  tools/train-venv/Scripts/python src/building/finetune_scans.py fetch 1500 150
                        tools/train-venv/Scripts/python src/building/finetune_scans.py train 8
Out: external/floorplan-to-3d/weights_scans/best.safetensors (+ config.yaml), results/plan_reading/finetune_log.csv
"""
import csv, io, json, random, sys, time, types
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
F3D = ROOT / "external" / "floorplan-to-3d"
DATA = ROOT / "data" / "datasets" / "cubicasa5k" / "trainval_scans"
SPLITS = ROOT / "data" / "datasets" / "cubicasa5k" / "raw" / "cubicasa5k"
URL = "https://zenodo.org/api/records/2613548/files/cubicasa5k.zip/content"
OUTW = F3D / "weights_scans"
LOG = ROOT / "results" / "plan_reading" / "finetune_log.csv"
SIZE = 512
MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
sys.path.insert(0, str(F3D / "src"))
sys.modules.setdefault("cairosvg", types.ModuleType("cairosvg"))       # svg rendering is not needed: we use the scans


def ids(split):
    return [l.strip().strip("/") for l in (SPLITS / (split + ".txt")).read_text().splitlines() if l.strip()]


def fetch(n_train, n_val):
    from remotezip import RemoteZip
    random.seed(7)
    pick = {"train": random.sample(ids("train"), n_train), "val": random.sample(ids("val"), n_val)}
    DATA.mkdir(parents=True, exist_ok=True)
    got = 0
    with RemoteZip(URL) as z:
        names = set(z.namelist())
        for split, lst in pick.items():
            for rel in lst:
                d = DATA / split / rel.replace("/", "_")
                if (d / "model.svg").exists():
                    got += 1
                    continue
                d.mkdir(parents=True, exist_ok=True)
                for f in ("F1_scaled.png", "model.svg"):
                    name = "cubicasa5k/%s/%s" % (rel, f)
                    if name in names:
                        (d / f).write_bytes(z.read(name))
                got += 1
                if got % 100 == 0:
                    print("  fetched", got, flush=True)
    print("plans:", got, "| disk:", round(sum(p.stat().st_size for p in DATA.rglob("*") if p.is_file()) / 1e6), "MB")


def letterbox(img, mask=None):
    s = SIZE / max(img.width, img.height)
    w, h = max(1, round(img.width * s)), max(1, round(img.height * s))
    canvas = Image.new("RGB", (SIZE, SIZE), tuple(int(255 * m) for m in MEAN))
    l, t = (SIZE - w) // 2, (SIZE - h) // 2
    canvas.paste(img.resize((w, h), Image.BILINEAR), (l, t))
    if mask is None:
        return canvas
    m = Image.new("L", (SIZE, SIZE), 0)
    m.paste(Image.fromarray(mask).resize((w, h), Image.NEAREST), (l, t))
    return canvas, np.asarray(m)


def load(d):
    from buildingcv.svg_to_mask import svg_to_mask
    img = Image.open(d / "F1_scaled.png").convert("RGB")
    mask = svg_to_mask(d / "model.svg", size=(img.width, img.height))
    return letterbox(img, mask)


def augment(img):
    if random.random() < 0.8:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.8, 1.15))
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.7, 1.3))
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.2)))
    if random.random() < 0.3:                                    # coloured plans: tint the paper and the ink
        a = np.asarray(img).astype(np.float32)
        a = a * np.array([random.uniform(0.8, 1.1) for _ in range(3)])
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return img


def to_tensor(img):
    import torch
    a = (np.asarray(img).astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(a.transpose(2, 0, 1).astype(np.float32))


def train(epochs):
    import torch, torch.nn as nn
    from buildingcv.model import build_model
    from safetensors.torch import load_file, save_file
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device:", dev, torch.cuda.get_device_name(0) if dev.type == "cuda" else "")
    tr = sorted((DATA / "train").glob("*"))
    va = sorted((DATA / "val").glob("*"))
    print("loading", len(tr), "train +", len(va), "val plans", flush=True)
    cache = {}

    def sample(d):
        if d not in cache:
            try:
                cache[d] = load(d)
            except Exception:
                cache[d] = None
        return cache[d]
    model = build_model(encoder_weights=None).to(dev)
    model.load_state_dict(load_file(str(F3D / "weights" / "best.safetensors")))
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor([0.5, 1.5, 2.0, 2.0], device=dev))   # walls/doors/windows are thin
    scaler = torch.amp.GradScaler(enabled=dev.type == "cuda")

    def evaluate():
        model.eval()
        inter, union = np.zeros(4), np.zeros(4)
        with torch.no_grad():
            for d in va:
                s = sample(d)
                if s is None:
                    continue
                img, m = s
                with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                    p = model(to_tensor(img)[None].to(dev)).argmax(1)[0].cpu().numpy()
                for c in range(4):
                    inter[c] += np.logical_and(p == c, m == c).sum()
                    union[c] += np.logical_or(p == c, m == c).sum()
        model.train()
        return inter / np.maximum(union, 1)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    iou0 = evaluate()
    print("before: IoU floor/wall/door/window", np.round(iou0, 3), flush=True)
    rows.append({"epoch": 0, "loss": "", "iou_floor": iou0[0], "iou_wall": iou0[1], "iou_door": iou0[2], "iou_window": iou0[3]})
    best = iou0[1]
    OUTW.mkdir(parents=True, exist_ok=True)
    (OUTW / "config.yaml").write_text((F3D / "weights" / "config.yaml").read_text())
    save_file(model.state_dict(), str(OUTW / "best.safetensors"), metadata={"epoch": "0", "note": "published weights, before fine-tuning"})
    bs = 6
    for ep in range(1, epochs + 1):
        t0, tot, n = time.time(), 0.0, 0
        random.shuffle(tr)
        for i in range(0, len(tr), bs):
            batch = [sample(d) for d in tr[i:i + bs]]
            batch = [b for b in batch if b is not None]
            if not batch:
                continue
            x = torch.stack([to_tensor(augment(img)) for img, _ in batch]).to(dev)
            y = torch.stack([torch.from_numpy(m.astype(np.int64)) for _, m in batch]).to(dev)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tot += float(loss) * len(batch)
            n += len(batch)
        sched.step()
        iou = evaluate()
        print("epoch %d: loss %.3f | IoU floor/wall/door/window %s | %.0f s" % (ep, tot / max(n, 1), np.round(iou, 3), time.time() - t0), flush=True)
        rows.append({"epoch": ep, "loss": round(tot / max(n, 1), 4), "iou_floor": iou[0], "iou_wall": iou[1], "iou_door": iou[2], "iou_window": iou[3]})
        if iou[1] > best:                                        # keep the epoch with the best wall IoU on the val scans
            best = iou[1]
            save_file(model.state_dict(), str(OUTW / "best.safetensors"), metadata={"epoch": str(ep), "val_wall_iou": "%.4f" % iou[1]})
        with open(LOG, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print("best val wall IoU %.3f (published weights %.3f)" % (best, iou0[1]))


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(int(sys.argv[2]), int(sys.argv[3]))
    else:
        train(int(sys.argv[2]))
