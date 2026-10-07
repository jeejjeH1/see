# Seismic ecosystem — motion graphic

A 16:9 (1920×1080, 60 fps, H.264 + AAC stereo) motion graphic for an X/Twitter post about the 11 fintechs building on [@SeismicSys](https://x.com/SeismicSys).

**Final video:** [`out/seismic-ecosystem.mp4`](out/seismic-ecosystem.mp4)

## Structure

Everything is cut to a 120 BPM grid (beat = 0.5s, bar = 2s), and the soundtrack is generated from the same cue list as the picture, so every hit lands on its frame.

| Time | Scene |
|---|---|
| 0:00 | Hook: "Neobanks. Payments. Credit. AI finance." cut on each beat, then "kept private." scrambles into place over a riser |
| 0:04 | Drop: flash and shake, the Seismic mark assembles, "11 fintechs are already building on Seismic." |
| 0:08 | Why Seismic: a public ledger gets shielded by a glitching scan line, $17M (led by a16z crypto), the stablecoin stack |
| 0:18 | Ecosystem grid: all 11 teams pop in on 16th notes |
| 0:22 | One 2-bar slide per team, with a wipe transition, logo slam and one row per beat |
| 1:06 | "11 teams. One pattern." then the Seismic sign-off |

**Sound:** an original track synthesized in `tools/soundtrack.py` (F minor, 120 BPM: kick, clap, hats, rolling bass, supersaw pad, arpeggio, plus risers, whooshes, impacts, glitches and UI ticks). It needs no samples and has no licensing strings attached. It's normalized to −14 LUFS.

Brand palette: Mauve `#825A6D`, Purple `#523542`, greys `#FCFCFC → #161616`. Type: Inter / Inter Display.

## Files

- `video/index.html`: the whole animation, driven by a deterministic timeline (`window.seek(t)`). Copy and timings live at the top of the script (`P` and the `S*_IN` constants).
- `assets/logos/src/*.png`: the logos as supplied. `assets/logos/*.svg`: vector traces of them (`tools/vectorize.py`), so they stay sharp at any size.
- `tools/render.js`: renders every frame with Playwright, dumps the timeline cues, builds the soundtrack and muxes everything with ffmpeg.
- `tools/soundtrack.py`: the music and sound design, generated from `out/cues.json`.

## Re-render

```bash
pip install numpy scipy pillow potracer    # potracer only needed to re-trace logos
python3 tools/vectorize.py

# needs playwright (Chromium) + ffmpeg
node tools/render.js                       # -> out/seismic-ecosystem.mp4
node tools/render.js --audio-only          # re-make just the soundtrack and remux
node tools/render.js --stills 3,12,30      # -> out/stills/*.png for quick review
```
