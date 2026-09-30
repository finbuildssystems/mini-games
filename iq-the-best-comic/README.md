# iQ The Best! — comic animation test

A 30-second animated test scene for the *iQ The Best!* comic: the shop that never has any stock.

## Files

- `iq-the-best-motion-comic.html` — **the main version.** The cover art is cut into a layer per character plus the title, and animated in code as puppets: entrances, head turns, blinks, talking, breathing, Freddie's leap, Jess's bat taps, Elena's stomps and hair, speech bubbles, sound effects, camera moves and a synthesised soundtrack. It loads its art from `assets/` beside it.
- `iq-the-best-animated.html` — the earlier 3D experiment with toy-like figures. Kept for reference; it does not match the cover's style.
- `tools/build_layers.py` — turns the cover into those layers (see below).
- `tools/render-video.mjs` — renders the motion comic to an MP4 with its soundtrack.

## How the cover becomes layers

1. **Separate the characters.** Segment Anything, with click prompts per character (`PROMPTS`), picks out each person; the `isnet-anime` matte sharpens the edges. Split lines (`ZONES`), gap rules (`GAPS`) and front-to-back overrides (`IN_FRONT`) clean up the places where people overlap.
2. **Rebuild the empty shop.** LaMa inpainting paints everyone out and fills the room from what surrounds them (floor tiles, pillar, stools). The back counters behind the characters reuse the cover's own white drawer unit (`CABINET`), and LaMa blends the joins.
3. **Complete each person.** Parts hidden behind someone else are filled in: Marcin's right side is mirrored from his left (`MIRROR`); Freddie's boot and Elena's hair behind Jess's bat are inpainted from their surroundings (`HIDDEN`).
4. **Upscale.** A 4x Real-ESRGAN anime pass sharpens the cover and the rebuilt areas, so close-ups stay crisp.
5. **Export.** `--export 2:assets` gives the web page's art (3 MB); `--export 4:assets4` gives full-resolution art for the video.

## Rebuilding the assets

`assets/` (the web page's art) and `source/cover.png` (the original cover) are committed here. To regenerate the art, or make the full-resolution `assets4/` for the video:

```sh
pip install "rembg[cpu]" opencv-python-headless pillow numpy torch
# models: big-lama.pt (github.com/Sanster/models releases, add_big_lama)
#         RealESRGAN_x4plus_anime_6B.pth (github.com/xinntao/Real-ESRGAN releases, v0.2.2.4)
python3 tools/build_layers.py source/cover.png --lama big-lama.pt --esrgan RealESRGAN_x4plus_anime_6B.pth \
  --export 2:assets --export 4:assets4
```

A full run takes about 25 minutes on four CPU cores; `--upscaled` reuses an existing 4x cover and `--reuse-plate` reuses the rebuilt room when only the characters change.

The puppet rigs (neck pivots, eyes, mouths, moving parts) and each character's entrance are in the `RIG` and `ENTER` tables of the HTML file, in the cover's own 1024 x 1536 pixel coordinates.

## Rendering the video

```sh
npm install playwright
IQ_ASSETS=assets4 node tools/render-video.mjs iq-the-best-motion-comic.mp4 --workers 4
```

This needs `ffmpeg` on the path (or `FFMPEG=/path/to/ffmpeg`). Output is 1080 x 1620 at 30 fps.

## Viewing it locally

The page loads its art from `assets/`, which browsers block when a file is opened directly. From this folder run `python3 -m http.server 8000` and open http://localhost:8000/iq-the-best-motion-comic.html.
