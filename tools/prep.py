"""Lift each source sheet off its backdrop into a real alpha channel.

Why alpha travels instead of a key colour: keying downstream forces the key to
be a hue the art does not contain, and no single hue is safe for everyone --
Mordemir's flame is green, Devilette's energy went purple, then cyan and pink.
The backdrop comes off once, here, with the best information available, and the
alpha goes with the art from then on.

How the alpha is found: a backdrop screen contaminates everything drawn over it,
so a soft glow really is part backdrop and belongs at part alpha. Measuring how
far a pixel leans toward the backdrop's hue gets that right; measuring distance
to the backdrop colour does not -- it calls a green-blended glow fully opaque
and leaves it green. Leaning is then removed from the colour as well (despill),
so edges and glows keep their own hue rather than a tint of the screen.

The backdrop colour is the single most common colour in the image, never
sampled from the border -- a sheet's own grid lines sit exactly there.

--keep-enclosed is for art that contains the backdrop's own hue, where a gap
between limbs cannot be told from an effect. It keeps every region the figure
encloses, at the cost of leaving backdrop in those gaps.

Writes raw<sheet>.png as RGBA.
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

LO, HI = 28, 95          # leaning below LO is fully opaque, above HI fully clear
DESPILL = 0.15           # fraction of the backdrop-hue excess left behind


def prep(src, out, keep_enclosed=False, bleed=14):
    f = np.array(Image.open(src).convert('RGB')).astype(np.float32)
    cols, counts = np.unique(f.astype(np.int16).reshape(-1, 3), axis=0, return_counts=True)
    bg = cols[counts.argmax()]
    dom = int(np.argmax(bg))                      # which channel the screen is
    others = [c for c in range(3) if c != dom]

    rest = np.maximum(f[..., others[0]], f[..., others[1]])
    lean = f[..., dom] - rest
    alpha = 1 - np.clip((lean - LO) / (HI - LO), 0, 1)

    # Despill: pull the screen's channel back down toward the other two.
    f[..., dom] = np.where(lean > 0, rest + lean * DESPILL, f[..., dom])

    clear = alpha < 0.5
    lab, _ = ndimage.label(clear)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    enclosed = clear & ~np.isin(lab, list(edge))
    if keep_enclosed:
        alpha[enclosed] = 1.0

    # Bleed opaque colour outward. Nothing sees these pixels, but the upscaler
    # does, and a hard edge against flat colour makes it invent a fringe.
    solid = alpha > 0.5
    if bleed and solid.any():
        idx = ndimage.distance_transform_edt(~solid, return_distances=False,
                                             return_indices=True)
        grow = ndimage.binary_dilation(solid, np.ones((3, 3)), iterations=bleed)
        f = np.where((~solid & grow)[..., None], f[tuple(idx)], f)

    rgba = np.dstack([f, alpha * 255]).clip(0, 255).astype(np.uint8)
    Image.fromarray(rgba, 'RGBA').save(out)
    soft = ((alpha > .03) & (alpha < .97)).mean()
    print(f'{src.split("/")[-1]}: screen {bg.astype(int).tolist()} on channel "{"RGB"[dom]}"  '
          f'art {100*solid.mean():.1f}%  soft {100*soft:.1f}%  '
          f'{int(enclosed.sum())} enclosed px {"kept" if keep_enclosed else "cleared"}')


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    keep = '--keep-enclosed' in sys.argv
    for k in 'ABC':
        prep(f'{d}/{k}_src.webp', f'{d}/raw{k}.png', keep_enclosed=keep)
