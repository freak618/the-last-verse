"""Flatten each source sheet's backdrop, then put it on this character's key colour.

Two separate things decide the key colour:

  * The BACKDROP the art arrived on, which this script removes by distance to
    the backdrop colour -- robust whatever hue it is, and immune to the trap
    where a dominance key eats an effect of the same hue as the backdrop.
  * The KEY COLOUR the rest of the pipeline cuts on, which has to be a colour
    the character's art does not contain. Mordemir's flame is green, so he
    keys magenta. Devilette's energy is purple, which sits right next to
    magenta, so she keys green.
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

KEYS = {'green': (0, 255, 0), 'magenta': (255, 0, 255)}


def prep(src, out, key='green', thresh=60, keep_enclosed=False):
    a = np.array(Image.open(src).convert('RGB')).astype(np.int16)
    # The backdrop is the single most common colour. Sampling the border instead
    # is thrown off by anything painted along the edge -- a sheet's own grid
    # lines, for one -- and a skewed backdrop colour makes the whole image read
    # as figure.
    cols, counts = np.unique(a.reshape(-1, 3), axis=0, return_counts=True)
    bg = cols[counts.argmax()].astype(float)
    d = np.sqrt(((a - bg) ** 2).sum(2))

    lab, _ = ndimage.label(d < thresh)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bgm = np.isin(lab, list(edge))          # only backdrop reachable from the border

    alpha = np.clip((d - thresh * .55) / (thresh * .45), 0, 1)
    alpha[bgm & (d < thresh * .55)] = 0
    if keep_enclosed:
        # Only for art that contains the backdrop's own hue -- Mordemir's green
        # flame on a green screen. Keeping every enclosed region saves the
        # effect, at the cost of leaving backdrop in gaps between limbs.
        alpha[~bgm] = 1.0
    enclosed = int((~bgm & (d < thresh)).sum())

    # de-spill: along the soft rim, pull the backdrop hue back toward the art
    f = a.astype(float)
    rim = (alpha > 0) & (alpha < 1)
    dom = int(np.argmax(bg))
    others = np.maximum.reduce([f[..., c] for c in range(3) if c != dom])
    f[..., dom] = np.where(rim & (f[..., dom] > others),
                           others + (f[..., dom] - others) * 0.15, f[..., dom])

    k = np.array(KEYS[key], float)
    comp = f * alpha[..., None] + k * (1 - alpha[..., None])
    Image.fromarray(comp.clip(0, 255).astype(np.uint8)).save(out)
    print(f'{src}: backdrop {bg.astype(int)} -> {key}   figure {100*(alpha>.5).mean():.1f}% '
          f'| {enclosed} enclosed px {"kept" if keep_enclosed else "removed"}')


if __name__ == '__main__':
    key = sys.argv[1] if len(sys.argv) > 1 else 'green'
    for sheet, src in (('A', 'img2.webp'), ('B', 'img4.webp'), ('C', 'img1.webp')):
        prep(f'/tmp/claude-0/b_devilette/{src}', f'/tmp/claude-0/b_devilette/raw{sheet}.png', key)
