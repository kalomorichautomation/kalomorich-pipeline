"""Fractal kaleidoscope renderer. Every frame is computed from scratch, so each video is original.

A video is one evolving cycle (default 4 min) rendered in parallel chunks, then looped to full length
with a slow hue drift by make_video.assemble, so no two loops look identical."""
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor

import numpy as np

OUT_W, OUT_H = 1920, 1080
SS = 1.5                        # supersampling factor for crisp lines
FPS = 30

# Curated looks: cosine palette a + b*cos(2pi(t+d))
PALETTES = {
    "Neon":    ([0.55, 0.40, 0.60], [0.45, 0.45, 0.40], [0.85, 0.20, 0.55]),
    "Ocean":   ([0.30, 0.50, 0.65], [0.30, 0.40, 0.35], [0.55, 0.65, 0.75]),
    "Emerald": ([0.40, 0.55, 0.40], [0.40, 0.45, 0.35], [0.30, 0.10, 0.60]),
    "Ember":   ([0.65, 0.40, 0.30], [0.35, 0.35, 0.30], [0.00, 0.12, 0.25]),
    "Cosmic":  ([0.50, 0.40, 0.60], [0.50, 0.40, 0.40], [0.70, 0.40, 0.10]),
    "Prism":   ([0.50, 0.50, 0.50], [0.50, 0.50, 0.50], [0.00, 0.33, 0.67]),
}


def params_for(seed: int) -> dict:
    """Deterministic look for a given seed."""
    rng = np.random.default_rng(seed)
    name = list(PALETTES)[seed % len(PALETTES)]
    return {
        "seed": seed,
        "palette": name,
        "seg": int(rng.choice([8, 10, 12, 12, 16])),
        "cx": float(rng.uniform(0.74, 0.82)),
        "cy": float(rng.uniform(0.54, 0.62)),
        "spin_frames": int(rng.choice([300, 450, 600])),   # all divide the cycle length
        "palette_cycles": int(rng.choice([2, 3])),
    }


class Field:
    def __init__(self, w, h):
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        self.X = (xs - w / 2 + 0.5) / h * 2.0
        self.Y = (ys - h / 2 + 0.5) / h * 2.0
        self.R0 = np.sqrt(self.X ** 2 + self.Y ** 2)
        self.A0 = np.arctan2(self.Y, self.X)
        self.vign = (1.0 - 0.55 * np.clip(self.R0 / 1.9, 0, 1) ** 2)[..., None]


def frame(i, n, p, F, iters=9):
    a_, b_, d_ = (np.float32(v) for v in PALETTES[p["palette"]])
    pal = lambda t: a_ + b_ * np.cos(6.28318 * (t[..., None] + d_))
    ph = 2 * np.pi * (i % p["spin_frames"]) / p["spin_frames"]
    P = 2 * np.pi * i / n
    s, c = np.float32(np.sin(ph)), np.float32(np.cos(ph))
    seg = 2 * np.pi / p["seg"]
    ang = np.abs(((F.A0 + ph) % seg) - seg / 2)
    r = F.R0 * (1.25 + 0.12 * c)
    zx, zy = r * np.cos(ang), r * np.sin(ang)
    cx = np.float32(p["cx"] + 0.04 * c + 0.05 * np.sin(P))
    cy = np.float32(p["cy"] + 0.04 * s + 0.05 * np.cos(2 * P))
    trap = np.full(F.R0.shape, 1e3, np.float32); line = trap.copy(); acc = np.zeros_like(F.R0)
    for k in range(iters):
        zx, zy = np.abs(zx), np.abs(zy)
        m = zx * zx + zy * zy + 1e-6
        zx, zy = zx / m - cx, zy / m - cy
        rr = np.sqrt(zx * zx + zy * zy)
        trap = np.minimum(trap, np.abs(rr - 0.55))
        if k < 6:
            line = np.minimum(line, np.minimum(np.abs(zx), np.abs(zy)))
        acc += np.exp(-3.0 * rr)
    t = 0.18 * acc + 0.9 * trap + ph / (2 * np.pi) + p["palette_cycles"] * P / (2 * np.pi)
    col = pal(t) * (0.35 + 0.65 * np.exp(-6.0 * trap))[..., None]
    col = col + 0.85 * np.exp(-line / 0.012)[..., None] * pal(t + 0.5)
    col += 0.35 * np.exp(-9 * F.R0 * F.R0)[..., None]
    col = np.clip(col * F.vign, 0, 1) ** 1.15
    return (col * 255).astype(np.uint8)


def _render_chunk(args):
    p, n, lo, hi, out, w, h = args
    F = Field(w, h)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(FPS), "-i", "-", "-vf", f"scale={OUT_W}:{OUT_H}:flags=area,format=yuv420p",
           "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", "-tune", "film", out + ".tmp.mp4"]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(lo, hi):
        ff.stdin.write(frame(i, n, p, F).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on chunk {lo}-{hi}")
    os.replace(out + ".tmp.mp4", out)
    return out


def render_cycle(p, out, seconds=240, workers=None, ss=SS):
    """Render one seamless evolving cycle to `out` (mp4, no audio)."""
    n = FPS * seconds
    workers = workers or os.cpu_count() or 2
    w, h = int(OUT_W * ss), int(OUT_H * ss)
    bounds = np.linspace(0, n, workers + 1).astype(int)
    parts = [f"{out}.part{k}.mp4" for k in range(workers)]
    jobs = [(p, n, int(bounds[k]), int(bounds[k + 1]), parts[k], w, h) for k in range(workers)]
    with ProcessPoolExecutor(workers) as ex:
        list(ex.map(_render_chunk, jobs))
    lst = out + ".txt"
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(x)}'\n" for x in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", out], check=True)
    for x in parts + [lst]:
        os.remove(x)
    return out


def still(p, i, n, path, ss=SS):
    from PIL import Image
    w, h = int(OUT_W * ss), int(OUT_H * ss)
    img = Image.fromarray(frame(i, n, p, Field(w, h)))
    img.resize((OUT_W, OUT_H), Image.LANCZOS).save(path)
    return path
