# The Backyard Ring, cut into layers

Every file here is the full size of the original painting (1672x941) and uses the same coordinates, so drawing them in order at one uniform scale rebuilds the painting exactly. Nothing is ever stretched on its own.

Back to front:

1. `background.webp`: yard, trailer, fence, banner, lights and trees, with the ring taken out
2. `mat.webp`: canvas and platform
3. `post_back_*`, `turnbuckles_back_*`
4. `rope_top_back`, `rope_middle_back`, `rope_bottom_back`: the back ropes
5. `rope_*_left_back`, `rope_*_right_back`: the far half of each side rope
6. **the fighters**
7. `rope_*_left_front`, `rope_*_right_front`: the near half of each side rope
8. `turnbuckles_front_*`, `post_front_*`
9. `apron.webp`: the front skirt with the logo

`front.webp` is layers 7-9 combined. The game draws the untouched painting (`stages/ring_lv.webp`) as the back and `stages/ring_lv_front.webp` (the same as `front.webp`) over the fighters, both with one transform. Side ropes split where they cross the fighters' line; `layers.json` has the split points and every rope's measured line and thickness. `build_ring.py` rebuilds all of it from the painting.
