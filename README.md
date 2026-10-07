# Seismic ecosystem — motion graphic

A 16:9 (1920×1080, 60 fps, H.264) motion graphic for an X/Twitter post about the 11 fintechs building on [@SeismicSys](https://x.com/SeismicSys).

**Final video:** [`out/seismic-ecosystem.mp4`](out/seismic-ecosystem.mp4)

## Structure

| Time | Scene |
|---|---|
| 0:00 | Intro: Seismic mark assembles, "11 fintechs are already building on Seismic." |
| 0:06 | Why Seismic: a public ledger gets shielded; $17M led by a16z crypto; the stablecoin stack |
| 0:17 | Ecosystem grid: all 11 teams |
| 0:22 | One slide per team (Specie, Promis, Brookwell, Via, Prism, DashX, Vend, Avvio, Pagga, Blend, Shift) |
| 1:11 | Outro: "11 teams. One pattern." and the Seismic sign-off |

Brand palette: Mauve `#825A6D`, Purple `#523542`, greys `#FCFCFC → #161616`. Type: Inter / Inter Display.

## Files

- `video/index.html`: the whole animation, driven by a deterministic timeline (`window.seek(t)`). Copy and timings live at the top of the script (`P` and the `S*_IN` constants).
- `assets/logos/src/*.png`: the logos as supplied. `assets/logos/*.svg`: vector traces of them (`tools/vectorize.py`), so they stay sharp at any size.
- `tools/render.js`: renders every frame with Playwright and encodes it with ffmpeg.

## Re-render

```bash
pip install potracer numpy pillow          # only needed to re-trace logos
python3 tools/vectorize.py

# needs playwright (Chromium) + ffmpeg
node tools/render.js                       # -> out/seismic-ecosystem.mp4
node tools/render.js --stills 3,12,30      # -> out/stills/*.png for quick review
```
