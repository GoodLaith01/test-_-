# The Deep City — 10 s underwater short

A man dives below the surface, breathing water as easily as air, and glides down
into a vast city on the ocean floor: glass-and-coral towers, a cable-stayed
bridge, and a curving highway full of moving cars.

**Final video:** [`the_deep_city.mp4`](the_deep_city.mp4) (1920×1080, 24 fps, 10 s, stereo AAC)

## How it was made

1. **Keyframes:** two photoreal stills generated with the Lupa connector
   (`nano-banana-pro`, 2752×1536): the city reveal (`assets/city.png`) and
   the dive (`assets/dive.png`, generated with the city image as a reference
   so the man looks the same in both).
2. **Layers:** `segment.py` cuts the swimmer out of each still (GrabCut guided
   by hand-placed body strokes) and inpaints a clean background plate.
3. **Animation:** `render.py` moves a virtual camera over the layers with
   parallax and adds procedural motion on every frame:
   - animated god rays, and light patterns rippling over the swimmer
   - flutter-kicking legs and breath bubbles rising from his mouth
   - drifting particles in true 3D perspective (rising past the camera as it descends, streaming outward as it glides forward)
   - headlights and taillights driving along the highway and bridge
   - water-refraction shimmer, bloom, color grade, chromatic aberration, vignette, film grain
4. **Sound:** `audio.py` synthesizes the soundtrack: the plunge, a muffled
   ocean bed, bubble pops timed to the picture, a dark drone that blooms into
   a major chord at the city reveal, a low boom on the cut, and a distant city hum.

## Rebuild

```bash
pip install opencv-python-headless scipy numpy
python3 segment.py assets                     # masks + background plates
python3 render.py assets video_noaudio.mp4    # ~8 min on 4 CPUs
python3 audio.py soundtrack.wav
ffmpeg -i video_noaudio.mp4 -i soundtrack.wav -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart the_deep_city.mp4
```
