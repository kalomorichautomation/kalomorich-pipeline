"""Original psychedelic soundtrack: 10 s seamless loops (120 BPM, 5 bars) in several variations,
arranged into a full-length track that keeps evolving. Each video gets its own key and seeds."""
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR, SECS, BPM = 48000, 10, 120
N = SR * SECS
SIX = int(SR * 60 / BPM / 4)          # one 16th note
STEPS = N // SIX                       # 80 sixteenths per loop

SCALE = [62, 63, 66, 67, 69, 70, 72, 74, 75, 78]          # D Phrygian dominant
SHAPES = [[0, 2, 4, 7, 4, 2, 5, 9], [1, 3, 5, 8, 5, 3, 6, 9], [0, 4, 7, 9, 7, 4, 2, 6],
          [1, 2, 5, 8, 9, 8, 5, 3], [0, 2, 4, 6, 7, 9, 7, 4]]


def _place(buf, at, sig):
    at %= N
    end = at + len(sig)
    if end <= N:
        buf[at:end] += sig
    else:
        k = N - at
        buf[at:] += sig[:k]
        buf[:end - N] += sig[k:]


def _saw(f, n):
    t = np.arange(n) / SR
    K = int(min(40, 18000 // f))
    return sum(np.sin(2 * np.pi * k * f * t) / k for k in range(1, K + 1)) * 0.6


def _lp(x, fc, order=4):
    return sosfilt(butter(order, min(fc, 0.45 * SR), "low", fs=SR, output="sos"), x)


def _hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def _midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _sweep(step):
    return 0.5 - 0.5 * np.cos(2 * np.pi * step / STEPS)


def loop(seed=5, transpose=0, kick=1, bass=1, hats=1, oct=0, rot=0, riser=1):
    """One seamless 10 s stereo loop as float array (N, 2)."""
    rng = np.random.default_rng(seed)
    L = np.zeros(N); R = np.zeros(N)

    n = int(0.35 * SR); t = np.arange(n) / SR
    kk = np.sin(2 * np.pi * (45 * t + 65 * 0.03 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.12) * 0.55
    for s in range(0, STEPS if kick else 0, 4):
        _place(L, s * SIX, kk); _place(R, s * SIX, kk)

    for s in range(STEPS if bass else 0):
        if s % 4 == 0:
            continue
        root = (38 if (s // 16) % 5 != 3 else 39) + transpose
        n = int(SIX * 0.9)
        env = np.exp(-np.arange(n) / (0.05 * SR)) * (1 - np.exp(-np.arange(n) / 40))
        note = _lp(_saw(_midi(root), n), 250 + 1400 * _sweep(s)) * env * 0.42
        _place(L, s * SIX, note); _place(R, s * SIX, note)

    aL = np.zeros(N); aR = np.zeros(N)
    for s in range(STEPS):
        m = SCALE[SHAPES[(s // 16 + rot) % 5][s % 8]] + 12 * oct + transpose
        n = int(SIX * 1.6)
        env = np.exp(-np.arange(n) / (0.09 * SR)) * (1 - np.exp(-np.arange(n) / 60))
        v = _saw(_midi(m), n) + 0.125 * np.sign(np.sin(2 * np.pi * _midi(m + 12) * np.arange(n) / SR))
        v = _lp(v, 900 + 4200 * _sweep(s + 20), order=2) * env * (0.22 if s % 2 == 0 else 0.15)
        pan = 0.5 + 0.4 * np.sin(2 * np.pi * s / 16)
        _place(aL, s * SIX, v * (1 - pan)); _place(aR, s * SIX, v * pan)

    def flanger(x, cycles):
        i = np.arange(N)
        d = (1.5 + 3.0 * (0.5 + 0.5 * np.sin(2 * np.pi * cycles * i / N))) * SR / 1000
        return 0.65 * x + 0.65 * np.interp((i - d) % N, i, x, period=N)

    aL, aR = flanger(aL, 2), flanger(aR, 3)
    oL, oR, sL, sR = aL.copy(), aR.copy(), aL, aR
    for _ in range(6):                                   # dotted-8th ping-pong delay, wrapping
        sL, sR = np.roll(sR, 3 * SIX) * 0.45, np.roll(sL, 3 * SIX) * 0.45
        sL, sR = _lp(sL, 5000, 1), _lp(sR, 5000, 1)
        oL += sL; oR += sR
    L += oL; R += oR

    n = int(0.06 * SR)
    for s in range(2, STEPS if hats else 0, 4):
        h = _hp(rng.standard_normal(n), 8000) * np.exp(-np.arange(n) / (0.015 * SR)) * 0.10
        _place(L, s * SIX, h * 0.8); _place(R, s * SIX, h)

    if riser:
        n = 16 * SIX
        z = rng.standard_normal(n); out = np.zeros(n); ch = SIX // 2
        for c in range(0, n, ch):
            out[c:c + ch] = _lp(_hp(z[c:c + ch], 300), 600 + 9000 * (c / n) ** 2, 2)
        out *= np.linspace(0, 1, n) ** 2 * 0.10
        out[-int(0.012 * SR):] *= np.linspace(1, 0, int(0.012 * SR))
        _place(L, 64 * SIX, out); _place(R, 64 * SIX, out)

    def reverb(x, s):
        n = int(2.2 * SR)
        ir = np.random.default_rng(s).standard_normal(n) * np.exp(-np.arange(n) / (0.45 * SR))
        ir = _hp(_lp(np.pad(ir, (0, N - n)), 7000, 2), 200)
        wet = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir), N)
        return wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max()

    L, R = L + 0.30 * reverb(L, seed + 16), R + 0.30 * reverb(R, seed + 17)
    mix = np.tanh(1.3 * np.stack([L, R], 1) / np.abs(np.stack([L, R])).max())
    return mix


def soundtrack(path, seed, minutes=60, transpose=0):
    """Arrange variations into a track of `minutes` length and write a 16-bit WAV."""
    V = {
        "full": loop(seed, transpose, riser=0),
        "full_rise": loop(seed, transpose),
        "full_b": loop(seed + 4, transpose, rot=2, riser=0),
        "breakdown": loop(seed, transpose, kick=0, bass=0, hats=0, riser=0),
        "break_rise": loop(seed + 2, transpose, kick=0, bass=0, hats=0, rot=1),
        "high": loop(seed + 6, transpose, oct=1, rot=3, riser=0),
        "groove": loop(seed + 8, transpose, rot=4, riser=0),
    }
    rms = lambda x: np.sqrt((x ** 2).mean())
    ref = rms(V["full"])
    for k, x in V.items():
        V[k] = x * (ref * (10 ** (-4 / 20) if k.startswith("break") else 1.0) / rms(x))
    mains = [["full"] * 5 + ["full_rise"], ["full_b"] * 5 + ["full_rise"],
             ["high"] * 5 + ["full_rise"], ["groove"] * 5 + ["full_rise"]]
    breaks = [["breakdown", "breakdown", "break_rise"], ["breakdown", "break_rise"]]
    total = minutes * 6
    rng = np.random.default_rng(seed)
    seq, last = ["breakdown", "breakdown", "break_rise"], -1
    while len(seq) < total:
        for _ in range(rng.integers(2, 4)):
            k = int(rng.choice([i for i in range(len(mains)) if i != last])); last = k
            seq += mains[k]
        seq += breaks[rng.integers(0, 2)]
    seq = seq[:total - 1] + ["breakdown"]
    out = np.concatenate([V[n] for n in seq])
    fi, fo = 4 * SR, 10 * SR
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    out *= 10 ** (-1 / 20) / np.abs(out).max()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((out * 32767).astype("<i2").tobytes())
    return path
