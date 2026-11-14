# The Deep City — vertical (1080×1920, 15 s) · Remotion

**Final video:** [`out/the_deep_city_vertical.mp4`](out/the_deep_city_vertical.mp4)
(1080×1920, 24 fps, 15 s, H.264 + AAC)

On-screen text: **THE DEEP CITY**. Palette: abyss navy `#041726`, glowing cyan `#5CE1FF`, warm gold `#FFC46B`.

## Scene order

| Time | Scene | What happens |
|---|---|---|
| 0–4.5 s | Dive | He dives toward the camera with no mask; bubbles stream from his mouth and the city glows far below. The camera tilts down and he rushes into the lens. |
| 4.7–9.5 s | City | Out of the deep blue, over his shoulder: a huge city with traffic moving on the bridges. The camera cranes up to the towers and domes. |
| 9.0–15 s | Street | Street level: people walk with real strides, feet planted on the ground (crossing, and walking away down the avenue) while swimmers and sharks move overhead. The camera follows them, then tilts up to the towers. |
| from 11.2 s | Title | "THE DEEP" (gold) and "CITY" (glowing cyan) with a gold rule; chime; fade to black. |

## Camera

`src/rig.ts` drives a cinematic virtual camera:
- each shot follows a smooth spline path with a soft ease, so it never stops or jerks mid-shot
- a low-frequency "operator float" adds drift, a slight roll and a breathing zoom, like a camera held by a diver
- the paths are chosen so the frame never leaves the image. `npx tsx scripts/check-camera.ts`
  verifies this for every frame and also checks smoothness
- focus pulls: from the man to the city in shot 2, focus settling in at the start of shot 3, and a defocus as he rushes into the lens
- 180° motion blur (`@remotion/motion-blur`, 6 samples) at 24 fps

## Character animation

`scripts/animate_layers.py` bakes the moving characters into video layers that Remotion plays inside the camera:
- **Street** (`public/street_anim.mp4`): each pedestrian is cut out with PP-HumanSeg (OpenCV Zoo), and the street behind them
  (including their old reflections) is rebuilt with LaMa inpainting (OpenCV Zoo). `scripts/gait.py` then makes them walk:
  - MediaPipe Pose (OpenCV Zoo) finds the shoulders, elbows, wrists, hips, knees, ankles, heels and toes
  - every pixel is skinned to the nearest bone, with narrow seams at the joints
  - in the gait model the stance foot stays planted while the hips move. The swing foot lifts, travels one stride and lands heel first.
    Knees come from 2-bone IK, the body bobs twice per cycle and the arms swing against the legs
  - people walking away shrink with perspective; the couple keep holding hands; dresses and skirts hang from the hips and follow the knees
  - moving reflections on the wet road
  - swimmers kick as they swim, and the sharks glide with a tail wave
- **Diver** (`public/dive_man_anim.webm`, with alpha): flutter kick, a slow breaststroke sweep of the arms, and hair moving in the water.
- **Man over the city** (`public/city_man_anim.webm`, with alpha): breathing and a slight head turn.

```bash
PPHUMANSEG=path/to/human_segmentation_pphumanseg_2023mar.onnx \
MPPOSE=path/to/pose_estimation_mediapipe_2023mar.onnx \
  python3 scripts/animate_layers.py path/to/inpainting_lama_2025jan.onnx
```
All three models are in the OpenCV Zoo (`models/human_segmentation_pphumanseg`, `models/pose_estimation_mediapipe`, `models/inpainting_lama`).

## Structure

- `src/rig.ts`: camera paths, float, and per-shot timing
- `src/DeepCity.tsx`: scenes, focus pulls, grade, title with light sweep, audio
- `src/effects.tsx`: god rays, bubbles, traffic lights with anamorphic streaks, 3D marine snow, grain, vignette
- `figma-src/`: the three photoreal 864×1536 keyframes generated with Figma's image generator
  (`gpt-image-2.5-sunburst`): `dive.png`, `city.png`, `street.png`
- `scripts/prep_figma.py`: upscales them 2× and cuts out the man (background plate + transparent cut-out) into `public/`
- `scripts/actors.py`, `scripts/lama.py`, `scripts/gait.py`, `scripts/animate_layers.py`: character cut-outs, inpainting, the skeleton walk model, and baked animation
- `public/`: the prepared layers plus `soundtrack_15s.wav`
- `scripts/audio15.py`: synthesizes the 15 s soundtrack: drone into a major chord, bubbles, a whoosh into the lens, an impact at the reveal, a riser and a chime for the title

## Commands

```bash
npm install
python3 scripts/prep_figma.py figma-src public           # rebuild layers from the Figma keyframes
npx tsx scripts/check-camera.ts                       # verify camera bounds and smoothness
npx remotion studio                                   # live preview
python3 scripts/audio15.py public/soundtrack_15s.wav  # rebuild the soundtrack
npx remotion render DeepCity out/the_deep_city_vertical.mp4
```

`remotion.config.ts` points Remotion at this environment's Chromium headless shell.
Change or remove `setBrowserExecutable` to use Remotion's own browser elsewhere.
