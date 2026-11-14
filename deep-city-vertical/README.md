# The Deep City — vertical (1080×1920, 15 s) · Remotion

**Final video:** [`out/the_deep_city_vertical.mp4`](out/the_deep_city_vertical.mp4)
(1080×1920, 30 fps, 15 s, H.264 + AAC)

On-screen text: **THE DEEP CITY**. Palette: abyss navy `#041726`, glowing cyan `#5CE1FF`, warm gold `#FFC46B`.

## Scene order

| Time | Scene | What happens |
|---|---|---|
| 0–3 s | Surface | The man dives under the sunlit surface with no mask; bubbles stream from his mouth; light rays sway. |
| 3–6 s | Go deeper | Push-in to a close-up of him breathing water; particles rise as the camera sinks; fade into deep navy. |
| 6–11 s | Reveal | The city emerges from the blue behind his shoulder; the camera pans right across the bridge, the traffic-filled highway and the glass towers. |
| 11–15 s | Title | Push-in on the towers; "THE DEEP" (gold) and "CITY" (glowing cyan) with a gold rule; chime; fade to black. |

## Structure

- `src/DeepCity.tsx`: scenes, camera moves, title, audio
- `src/effects.tsx`: god rays, bubbles, highway and bridge traffic, 3D marine snow, grain, vignette
- `public/`: layers exported from the photoreal keyframes in `../underwater-city/assets`
  (background plates and transparent cut-outs of the man), plus `soundtrack_15s.wav`
- `scripts/audio15.py`: synthesizes the 15 s soundtrack

## Commands

```bash
npm install
npx remotion studio                                   # live preview
python3 scripts/audio15.py public/soundtrack_15s.wav  # rebuild the soundtrack
npx remotion render DeepCity out/the_deep_city_vertical.mp4
```

`remotion.config.ts` points Remotion at this environment's Chromium headless shell.
Change or remove `setBrowserExecutable` to use Remotion's own browser elsewhere.
