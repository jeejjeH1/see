"""Synthesise an original soundtrack for the video, locked to its timeline.

Reads out/cues.json (timing constants + per-event cues dumped by tools/render.js)
and writes out/soundtrack.wav (44.1 kHz stereo). Everything here is generated from
scratch with numpy/scipy, so the track is royalty-free.

120 BPM, F minor: Fm - Db - Ab - Eb, one chord per bar.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 44100
RNG = np.random.default_rng(7)

data = json.loads((ROOT / "out" / "cues.json").read_text())
T = data["timing"]
CUES = data["cues"]
BEAT = 60 / T["BPM"]
BAR = BEAT * 4
S16 = BEAT / 4
DROP, WHY, ENC, PRIV, MONEY = T["DROP"], T["WHY"], T["ENC"], T["PRIV"], T["MONEY"]
GRID, SLIDES, OUTRO, FINAL, END = T["GRID"], T["SLIDES"], T["OUTRO"], T["FINAL"], T["END"]
LEN = int((END + 0.5) * SR)


# ---------------------------------------------------------------- helpers
def bus():
    return np.zeros((2, LEN))


def sos(kind, fc, order=2):
    return butter(order, fc, kind, fs=SR, output="sos")


def filt(x, kind, fc, order=2):
    return sosfilt(sos(kind, fc, order), x)


def add(b, x, t, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= LEN:
        return
    if i < 0:
        x, i = x[-i:], 0
    n = min(len(x), LEN - i)
    a = (pan + 1) * np.pi / 4
    b[0, i:i + n] += x[:n] * gain * np.cos(a)
    b[1, i:i + n] += x[:n] * gain * np.sin(a)


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def saw(f, t, phase=0.0):
    return 2 * ((f * t + phase) % 1) - 1


def noise(dur):
    return RNG.standard_normal(int(dur * SR))


def sweep_filter(x, kind, f0, f1, block=512, curve=2.0):
    """Block-wise time-varying filter (fine for noise and pads)."""
    out = np.zeros_like(x)
    nb = (len(x) + block - 1) // block
    zi = np.zeros((1, 2))
    for k in range(nb):
        fc = f0 * (f1 / f0) ** ((k / max(1, nb - 1)) ** curve)
        if kind == "bandpass":
            s = butter(1, [max(20, fc * 0.7), min(SR / 2 * 0.95, fc * 1.4)], "bandpass", fs=SR, output="sos")
        else:
            s = butter(2, min(fc, SR / 2 * 0.95), kind, fs=SR, output="sos")
        seg = x[k * block:(k + 1) * block]
        y, zi = sosfilt(s, seg, zi=zi)
        out[k * block:k * block + len(seg)] = y
    return out


def beats(a, b, step=BEAT, offset=0.0):
    t = a + offset
    while t < b - 1e-6:
        yield round(t, 6)
        t += step


def in_ranges(t, ranges):
    return any(a <= t < b for a, b in ranges)


CHORDS = [  # (bass root, chord tones) one per bar from the drop
    (41, [53, 56, 60]),  # Fm
    (37, [49, 53, 56]),  # Db
    (44, [51, 56, 60]),  # Ab
    (39, [51, 55, 58]),  # Eb
]


def chord_at(t):
    if t < DROP:
        return CHORDS[0]
    return CHORDS[int((t - DROP) // BAR) % 4]


# ---------------------------------------------------------------- instruments
def kick(gain=1.0):
    t = tt(0.45)
    f = 45 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.22)
    click = filt(noise(0.45), "highpass", 3000) * np.exp(-t / 0.004) * 0.35
    return np.tanh((body + click) * 1.6) * gain


def snare(gain=1.0, dur=0.22):
    t = tt(dur)
    n = filt(noise(dur), "bandpass", [1200, 7000]) * np.exp(-t / 0.07)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05) * 0.6
    return (n + tone) * gain


def clap(gain=1.0):
    t = tt(0.3)
    env = np.zeros_like(t)
    for d in (0, 0.011, 0.022):
        m = t >= d
        env[m] += np.exp(-(t[m] - d) / (0.012 if d < 0.02 else 0.09))
    return filt(noise(0.3), "bandpass", [900, 5000]) * env * gain


def hat(dur=0.05, gain=1.0):
    t = tt(dur * 3)
    return filt(noise(dur * 3), "highpass", 7500) * np.exp(-t / dur) * gain


def pluck(m, dur=0.22, bright=3500):
    t = tt(dur)
    f = hz(m)
    x = saw(f, t) + 0.5 * saw(f * 1.005, t, 0.3)
    hi = filt(x, "lowpass", bright)
    lo = filt(x, "lowpass", 700)
    k = np.exp(-t / 0.05)
    return (hi * k + lo * (1 - k)) * np.exp(-t / (dur * 0.45)) * np.minimum(1, t / 0.003)


def supersaw(notes, dur, cutoff, voices=5, detune=0.012):
    t = tt(dur)
    x = np.zeros_like(t)
    for m in notes:
        for v in range(voices):
            d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * detune
            x += saw(hz(m) * (1 + d), t, RNG.random())
    x /= len(notes) * voices
    if isinstance(cutoff, tuple):
        x = sweep_filter(x, "lowpass", cutoff[0], cutoff[1], curve=1.5)
    else:
        x = filt(x, "lowpass", cutoff)
    a = np.minimum(1, t / 0.08) * np.minimum(1, (dur - t) / 0.12)
    return x * a


def bass_note(m, dur, cutoff=420):
    t = tt(dur)
    f = hz(m)
    x = saw(f, t) * 0.7 + np.sin(2 * np.pi * f * t) * 0.8
    x = filt(x, "lowpass", cutoff)
    a = np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))
    return np.tanh(x * a * 1.5)


def sub(m, dur):
    t = tt(dur)
    return np.sin(2 * np.pi * hz(m) * t) * np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.1)


def boom(size=1.0):
    d = 2.2 * size
    t = tt(d)
    f = 32 + 70 * np.exp(-t / 0.12)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.55 * size))
    hit = filt(noise(d), "lowpass", 2500) * np.exp(-t / 0.09) * 0.8
    crash = filt(noise(d), "highpass", 4500) * np.exp(-t / (0.9 * size)) * 0.35
    return np.tanh((s * 1.3 + hit) * 1.2) + crash


def riser(dur):
    t = tt(dur)
    n = sweep_filter(noise(dur), "bandpass", 250, 7000, curve=1.6)
    f = 110 * 2 ** (2.5 * (t / dur) ** 1.4)
    tone = filt(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)), "lowpass", 3000) * 0.18
    env = (t / dur) ** 2.2
    return (n * 1.2 + tone) * env


def whoosh(dur=0.5):
    t = tt(dur)
    x = noise(dur)
    up = sweep_filter(x, "bandpass", 400, 5000, curve=1.0)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2 * np.exp(-t / dur)
    return up * env * 1.8


def tick(i=0):
    t = tt(0.06)
    f = 1700 + 140 * (i % 5)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.012) + filt(noise(0.06), "highpass", 6000) * np.exp(-t / 0.003) * 0.4)


PENTA = [0, 3, 5, 7, 10, 12, 15, 17, 19, 22, 24, 27]


def pop(i=0):
    t = tt(0.18)
    base = hz(77 + PENTA[i % len(PENTA)])
    f = base * (0.75 + 0.25 * (1 - np.exp(-t / 0.01)))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.06)


def glitch(dur):
    n = int(dur * SR)
    x = np.zeros(n)
    i = 0
    while i < n:
        seg = int(RNG.uniform(0.012, 0.05) * SR)
        kind = RNG.integers(0, 3)
        tt_ = np.arange(seg) / SR
        if kind == 0:
            y = np.sign(np.sin(2 * np.pi * RNG.uniform(200, 2400) * tt_))
        elif kind == 1:
            y = np.round(RNG.standard_normal(seg) * 3) / 3
        else:
            y = np.zeros(seg)
        x[i:i + seg] = y[: max(0, min(seg, n - i))]
        i += seg
    return filt(x, "lowpass", 6000) * 0.5


# ---------------------------------------------------------------- arrangement
drums, bass, music, sfx, verb_send = bus(), bus(), bus(), bus(), bus()
kick_times = []

GROOVE = [(DROP, WHY), (PRIV, OUTRO - 0.5)]
LIGHT = [(WHY, PRIV)]                        # breakdown: no kick
for t in beats(0, END):
    if in_ranges(t, GROOVE):
        add(drums, kick(), t, 0.95)
        kick_times.append(t)
        bi = int(round((t - DROP) / BEAT)) % 4
        if bi in (1, 3):
            add(drums, clap(), t, 0.45, 0.05)
            add(drums, snare(dur=0.18), t, 0.25)
    if in_ranges(t, GROOVE + LIGHT):
        add(drums, hat(0.06), t + BEAT / 2, 0.22 if in_ranges(t, LIGHT) else 0.32, 0.25)
    if in_ranges(t, [(SLIDES, OUTRO - 0.5)]):   # 16th shaker over the slides
        for k in (1, 3):
            add(drums, hat(0.025), t + k * S16, 0.12 if t < SLIDES + 16 else 0.17, -0.3)
    if in_ranges(t, [(SLIDES + 16, OUTRO - 0.5)]) and int(round((t - DROP) / BEAT)) % 2 == 1:
        add(drums, hat(0.18), t + BEAT / 2, 0.12, 0.3)   # open hat lift

# snare rolls into each drop
for (a, b) in [(DROP - 2, DROP - 0.125), (OUTRO - 2, OUTRO - 0.125), (PRIV - 1, PRIV - 0.125)]:
    t, k = a, 0
    while t < b:
        p = (t - a) / (b - a)
        step = BEAT / 2 if p < 0.5 else (S16 if p < 0.85 else S16 / 2)
        add(drums, snare(dur=0.12), t, 0.08 + 0.32 * p ** 1.5, 0.1 * (-1) ** k)
        t += step
        k += 1

# bass: rolling 16ths in the groove, long notes in the breakdown
for t in beats(0, END, S16):
    root, _ = chord_at(t)
    pos = int(round((t - DROP) / S16)) % 4
    if in_ranges(t, GROOVE) and pos != 0:
        m = root + (12 if pos == 2 else 0)
        add(bass, bass_note(m, S16 * 0.95, 380 + 140 * (pos == 2)), t, 0.55)
for t in beats(WHY, PRIV, BAR):
    add(bass, bass_note(chord_at(t)[0], BAR * 0.98, 250), t, 0.5)
for t in beats(OUTRO, FINAL, BAR):
    add(bass, sub(chord_at(t)[0] + 12, BAR), t, 0.45)
add(bass, sub(41 + 12, END - FINAL), FINAL, 0.55)
add(bass, sub(41, 1.2), DROP, 0.6)

# pad
for t in beats(0, END, BAR):
    _, notes = chord_at(t)
    v = notes + [notes[0] + 12]
    if t < DROP - 2:
        p = supersaw(v, BAR, 700)
    elif t < DROP:
        p = supersaw(v, BAR, (700, 5000))
    elif FINAL <= t:
        p = supersaw(CHORDS[0][1] + [65, 72], min(BAR, END - t + 0.3), 2600)
    elif in_ranges(t, LIGHT):
        p = supersaw(v, BAR, 1400)
    elif in_ranges(t, [(OUTRO, FINAL)]):
        p = supersaw(v, BAR, 1800)
    else:
        p = supersaw(v, BAR, 2600)
    add(music, p, t, 0.42, 0)
    add(verb_send, p, t, 0.25)

# arp: 16th plucks, chord tones walking up
ARP = [0, 1, 2, 3, 1, 2, 3, 2]
for t in beats(DROP, FINAL, S16):
    if in_ranges(t, [(OUTRO - 0.5, OUTRO)]):
        continue
    _, notes = chord_at(t)
    tones = [notes[0] + 12, notes[1] + 12, notes[2] + 12, notes[0] + 24]
    k = int(round((t - DROP) / S16))
    m = tones[ARP[k % len(ARP)]]
    g = 0.17 if not in_ranges(t, LIGHT) else 0.13
    bright = 2600 if t < SLIDES else 3600
    x = pluck(m, 0.2, bright)
    pan = 0.35 if k % 2 else -0.35
    add(music, x, t, g, pan)
    for d, fb in ((3 * S16, 0.35), (6 * S16, 0.18)):   # ping-pong delay
        add(music, x, t + d, g * fb, -pan)
    add(verb_send, x, t, g * 0.4)

# ---------------------------------------------------------------- cues -> sfx
for c in CUES:
    t, k, v = c["t"], c["k"], c["v"]
    if k == "hit":
        add(sfx, kick(), t, 0.7)
        add(sfx, snare(dur=0.25), t, 0.18)
        add(sfx, boom(0.35), t, 0.25)
        add(verb_send, snare(dur=0.25), t, 0.3)
    elif k == "tick":
        add(sfx, tick(int(v)), t, 0.16, 0.2 * ((int(v) % 3) - 1))
    elif k == "pop":
        add(sfx, pop(int(v)), t, 0.22, -0.4 + 0.08 * (int(v) % 11))
        add(verb_send, pop(int(v)), t, 0.15)
    elif k == "glitch":
        add(sfx, glitch(max(0.2, v)), t, 0.32)
    elif k == "riser":
        add(sfx, riser(v), t, 0.42)
        add(verb_send, riser(v), t, 0.2)
    elif k in ("whoosh", "swish"):
        w = whoosh(0.45 if k == "whoosh" else 0.32)
        n = len(w)
        pan = np.linspace(0.8, -0.8, n)
        i = int(t * SR)
        m_ = min(n, LEN - i)
        a = (pan[:m_] + 1) * np.pi / 4
        sfx[0, i:i + m_] += w[:m_] * 0.42 * np.cos(a)
        sfx[1, i:i + m_] += w[:m_] * 0.42 * np.sin(a)
    elif k in ("impact", "drop", "final"):
        size = {"impact": 0.8, "drop": 1.2, "final": 1.5}[k]
        b = boom(size)
        add(sfx, b, t, 0.8)
        add(verb_send, b, t, 0.5)
        if k != "impact":
            kick_times.append(t)

# ---------------------------------------------------------------- mix
# sidechain pump from every kick
env = np.ones(LEN)
for kt in sorted(kick_times):
    i = int(kt * SR)
    n = min(int(0.4 * SR), LEN - i)
    d = np.arange(n) / SR
    env[i:i + n] = np.minimum(env[i:i + n], 1 - 0.6 * np.exp(-d / 0.12))
bass *= env
music *= 0.35 + 0.65 * env

ir_t = tt(2.2)
ir = [RNG.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.55) for _ in range(2)]
verb = np.stack([fftconvolve(filt(verb_send[c], "highpass", 300), ir[c])[:LEN] for c in range(2)]) * 0.035

drums *= 0.8
music *= 2.6
verb *= 0.4
mix = drums + bass + music + sfx + verb
mix = np.stack([filt(mix[c], "highpass", 28) for c in range(2)])

# fade in the first few ms, fade out the tail
fade_out = np.ones(LEN)
fo = int((END - 2.5) * SR)
fade_out[fo:] = np.linspace(1, 0, LEN - fo) ** 1.5
mix *= fade_out

for name, b in (("drums", drums), ("bass", bass), ("music", music), ("sfx", sfx), ("verb", verb)):
    print(f"{name:6s} rms {20 * np.log10(np.sqrt(np.mean(b ** 2)) + 1e-9):6.1f} dB", file=sys.stderr)

mix = np.tanh(mix * 0.9) / np.tanh(0.9)
mix /= np.max(np.abs(mix)) / 0.89
wavfile.write(ROOT / "out" / "soundtrack.wav", SR, (mix.T * 32767).astype(np.int16))
print("wrote out/soundtrack.wav", file=sys.stderr)
