"""Turn the flat green backdrop into alpha, then composite onto magenta.

The flame is green too, so a green-dominance key eats it. The backdrop is a
single flat colour though, so distance to THAT colour separates cleanly, and
keeping only border-connected background guarantees nothing enclosed by the
figure (or by the flame) is ever removed.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

im = Image.open('/tmp/claude-0/b_mord3/newB.png').convert('RGB')
a = np.array(im).astype(np.int16)
H, W = a.shape[:2]

bg = np.median(np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3),
                               a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)]), 0)
print('backdrop', bg)

d = np.sqrt(((a - bg) ** 2).sum(2))
for t in (30, 45, 60, 80, 110):
    print(f'  dist<{t:3}: {(d < t).mean() * 100:5.1f}% of pixels')

T = 60
raw = d < T
lab, n = ndimage.label(raw)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
bgm = np.isin(lab, list(border))
print(f'background {bgm.mean()*100:.1f}%  (dropped {(raw & ~bgm).sum()} enclosed px back to the figure)')

# soft edge: alpha ramps over the last few units of distance to the backdrop
alpha = np.clip((d - T * .55) / (T * .45), 0, 1)
alpha[bgm & (d < T * .55)] = 0
alpha = np.where(bgm | (alpha < 1), alpha, 1.0)
solid = ~bgm & (d >= T)
alpha[solid] = 1.0

# de-spill: inside the soft rim, pull green back down to the other channels
r, g, b = a[..., 0].astype(float), a[..., 1].astype(float), a[..., 2].astype(float)
rim = (alpha > 0) & (alpha < 1)
mx = np.maximum(r, b)
g2 = np.where(rim & (g > mx), mx + (g - mx) * 0.15, g)
rgb = np.stack([r, g2, b], -1)

# composite onto magenta so the rest of the pipeline keys magenta as it now does
MAG = np.array([255., 0., 255.])
out = rgb * alpha[..., None] + MAG * (1 - alpha[..., None])
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save('/tmp/claude-0/b_mord3/rawB.png')

rgba = np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)
Image.fromarray(rgba, 'RGBA').save('/tmp/claude-0/b_mord3/B_rgba.png')
print('wrote rawB.png (on magenta) and B_rgba.png (true alpha)')
