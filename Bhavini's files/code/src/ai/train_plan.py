"""Nomad - train NOMAD's plan AI: a U-Net that fills a flat's space with rooms (our own code, PyTorch).

Input (10 pictures, 80 x 80, 0,25 m per pixel): the flat's rectangle; its window rows (front and back); the entrance;
the distance from the windows and from the entrance; the number of bedrooms (4 one-hot pictures).
Output: for every pixel, which of 9 classes it is (outside, wall, living, bedroom 1, bedroom, kitchen, bath, hall, storage).
Loss: cross-entropy, rarer rooms weighted up. 95 % of the flats train, 5 % (whole flats, never seen) check it.
Run (GPU): tools/train-venv/Scripts/python.exe src/ai/train_plan.py [epochs]
Out: results/ai/plan_unet.pt (best on the check set), results/ai/train_log.csv
"""
import csv, math, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "ai"
PX, N, K = 0.25, 80, 9


def conditions(C):
    """C rows: W, D, lit front, lit back, entrance x, y, bedrooms, source -> (n, 10, N, N) float tensor."""
    n = C.shape[0]
    yy, xx = torch.meshgrid(torch.arange(N, dtype=torch.float32), torch.arange(N, dtype=torch.float32), indexing="ij")
    xx, yy = (xx + 0.5) * PX, (yy + 0.5) * PX
    W, D = C[:, 0].view(n, 1, 1), C[:, 1].view(n, 1, 1)
    inside = ((xx < W) & (yy < D)).float()
    front = (C[:, 2].view(n, 1, 1) > 0.5) & (yy < 2 * PX) & (xx < W)
    back = (C[:, 3].view(n, 1, 1) > 0.5) & (yy > D - 2 * PX) & (yy < D) & (xx < W)
    ex, ey = C[:, 4].view(n, 1, 1), C[:, 5].view(n, 1, 1)
    de = torch.sqrt((xx - ex) ** 2 + (yy - ey) ** 2)
    ent = (de < 0.75).float()
    dwin = torch.where(C[:, 3].view(n, 1, 1) > 0.5, torch.minimum(yy, (D - yy).clamp(min=0)), yy) / 10.0
    beds = torch.stack([(C[:, 6] == b).float().view(n, 1, 1).expand(n, N, N) * inside for b in range(4)], 1)
    return torch.cat([torch.stack([inside, front.float(), back.float(), ent, dwin * inside, de / 20.0 * inside], 1), beds], 1)


def block(a, b):
    return nn.Sequential(nn.Conv2d(a, b, 3, padding=1), nn.GroupNorm(8, b), nn.SiLU(), nn.Conv2d(b, b, 3, padding=1), nn.GroupNorm(8, b), nn.SiLU())


class UNet(nn.Module):
    def __init__(self, cin=10, k=K, w=48):
        super().__init__()
        self.e1, self.e2, self.e3, self.e4 = block(cin, w), block(w, 2 * w), block(2 * w, 4 * w), block(4 * w, 8 * w)
        self.u3, self.d3 = nn.ConvTranspose2d(8 * w, 4 * w, 2, 2), block(8 * w, 4 * w)
        self.u2, self.d2 = nn.ConvTranspose2d(4 * w, 2 * w, 2, 2), block(4 * w, 2 * w)
        self.u1, self.d1 = nn.ConvTranspose2d(2 * w, w, 2, 2), block(2 * w, w)
        self.out = nn.Conv2d(w, k, 1)

    def forward(self, x):
        a = self.e1(x)
        b = self.e2(Fn.max_pool2d(a, 2))
        c = self.e3(Fn.max_pool2d(b, 2))
        d = self.e4(Fn.max_pool2d(c, 2))
        c = self.d3(torch.cat([self.u3(d), c], 1))
        b = self.d2(torch.cat([self.u2(c), b], 1))
        a = self.d1(torch.cat([self.u1(b), a], 1))
        return self.out(a)


def miou(pred, y, inside):
    ious = []
    for k in range(1, K):
        p, t = (pred == k) & inside, (y == k) & inside
        u = (p | t).sum().item()
        if u:
            ious.append((p & t).sum().item() / u)
    return float(np.mean(ious))


def main(epochs=40):
    dev = "cuda"
    z = np.load(OUT / "plan_set.npz")
    Y, C = torch.from_numpy(z["Y"].astype(np.int64)), torch.from_numpy(z["C"])
    n = len(Y)
    flat = torch.arange(n) // 2                                  # a flat and its mirror stay on the same side
    g = torch.Generator().manual_seed(0)
    test_flats = torch.randperm(int(flat.max()) + 1, generator=g)[: (n // 2) // 20]
    te = torch.isin(flat, test_flats)
    tr_idx, te_idx = torch.where(~te)[0], torch.where(te)[0]
    freq = torch.bincount(Y[tr_idx].view(-1), minlength=K).float()
    wts = (freq.sum() / (freq + 1)).sqrt()
    wts = (wts / wts.mean()).to(dev)
    wts[0] = 0.2
    net = UNet().to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    steps = epochs * math.ceil(len(tr_idx) / 64)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=steps)
    scaler = torch.amp.GradScaler()
    best, log = 0.0, []
    print("train %d, check %d (whole flats never seen), %.1f M weights" % (len(tr_idx), len(te_idx), sum(p.numel() for p in net.parameters()) / 1e6), flush=True)
    for ep in range(epochs):
        t0, tot = time.time(), 0.0
        net.train()
        perm = tr_idx[torch.randperm(len(tr_idx))]
        for i in range(0, len(perm), 64):
            b = perm[i:i + 64]
            x, y = conditions(C[b]).to(dev), Y[b].to(dev)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = Fn.cross_entropy(net(x), y, weight=wts)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sch.step()
            tot += loss.item() * len(b)
        net.eval()
        accs, ious = [], []
        with torch.no_grad():
            for i in range(0, len(te_idx), 256):
                b = te_idx[i:i + 256]
                x, y = conditions(C[b]).to(dev), Y[b].to(dev)
                pred = net(x).argmax(1)
                inside = x[:, 0] > 0.5
                accs.append(((pred == y) & inside).sum().item() / inside.sum().item())
                ious.append(miou(pred, y, inside))
        acc, mi = float(np.mean(accs)), float(np.mean(ious))
        log.append({"epoch": ep + 1, "loss": round(tot / len(tr_idx), 4), "pixel_acc": round(acc, 4), "mIoU": round(mi, 4), "s": round(time.time() - t0, 1)})
        print(log[-1], flush=True)
        if mi > best:
            best = mi
            torch.save({"state": net.state_dict(), "classes": [str(c) for c in z["classes"]], "px": PX, "n": N}, OUT / "plan_unet.pt")
    with open(OUT / "train_log.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)
    print("best check-set mIoU %.3f" % best)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
