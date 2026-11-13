"""Remove drawn grid lines from a sheet that ships with its cell borders painted on.

The ungridded export of this sheet staggers its rows, so running figures spill
into the band below and the cutter clips them at the knees. The gridded export
keeps every figure inside its own cell, but the painted borders would read as
art. Those lines are thin, straight and near-black, so they are found by looking
for whole rows and columns that are dark, then filled in from the nearest clean
row or column on either side.
"""
import numpy as np
from PIL import Image

SRC = '/tmp/claude-0/b_devilette/img3.webp'
OUT = '/tmp/claude-0/b_devilette/img3_clean.png'

a = np.array(Image.open(SRC).convert('RGB')).astype(np.int16)
H, W = a.shape[:2]
dark = a.max(2) < 90

rows = np.where(dark.mean(1) > 0.75)[0]
cols = np.where(dark.mean(0) > 0.75)[0]
print('grid rows', rows.tolist())
print('grid cols', cols.tolist())


def fill(ax_idx, axis):
    """Replace each line with the nearest clean line on either side."""
    bad = np.zeros(a.shape[axis], bool)
    bad[ax_idx] = True
    # widen by one on each side: the painted line has a soft edge
    bad |= np.roll(bad, 1) | np.roll(bad, -1)
    good = np.where(~bad)[0]
    for i in np.where(bad)[0]:
        j = good[np.argmin(np.abs(good - i))]
        if axis == 0:
            a[i] = a[j]
        else:
            a[:, i] = a[:, j]
    return int(bad.sum())


n = fill(rows, 0) + fill(cols, 1)
Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(OUT)

left = (a.max(2) < 90)
print(f'filled {n} lines; dark pixels left {left.sum()} '
      f'({100*left.mean():.2f}% - her boots and horns are legitimately dark)')
