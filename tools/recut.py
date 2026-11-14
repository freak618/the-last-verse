"""Replace an existing fighter's select-screen cutout with new art.

addcut2.py only adds a fighter who has no cutout yet. This repoints one who
already has one at freshly pasted frames. The old frames stay in the atlas
unreferenced -- repacking the whole atlas would move every other fighter's
rects, which is a far larger risk than a few unused pixels.

    python3 -I recut.py <id> <transparent.png>

The source must already have an alpha channel. Art that arrives on a backdrop
goes through prep.py (a colour screen) or a distance key (a neutral one) first.
"""
import base64
import io
import json
import sys
import numpy as np
from PIL import Image

HTML = '/home/claude/lastverse.html'
HH, HIP = 276, 138
HEAD = 150.0

cid, src = sys.argv[1], sys.argv[2]

s = open(HTML, encoding='utf-8').read()
i = s.index('const ASSET=')
j = s.index('\n', i)
line = s[i:j]
A = json.loads(line[len('const ASSET='):].rstrip(';'))
cm = A['cutsMeta']
orig_meta = json.loads(json.dumps(cm))
assert ('"cutsMeta":' + json.dumps(cm, separators=(',', ':'))) in line
assert cid in cm['chars'], f'{cid} has no cutout yet -- use addcut2.py'

cuts = Image.open(io.BytesIO(base64.b64decode(A['cuts'].split(',', 1)[1]))).convert('RGBA')
atlas_h0 = cuts.height
F = cm['frames']
yF = max(f[1] for f in F if f[3] == HH)
yU, yL = yF + HH + 2, yF + HH + 2 + 146 + 2
x = max(f[0] + f[2] for f in F if f[1] == yF) + 4

im = Image.open(src).convert('RGBA')
al = np.asarray(im)[..., 3]
tp = (al < 20).mean()
assert tp > 0.3, f'background is not transparent ({tp:.0%} clear)'
ys, xs = np.where(al > 20)
im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
w = round(im.width * HH / im.height)
im = im.resize((w, HH), Image.LANCZOS)

a = np.asarray(im)[..., 3].astype(np.float32) / 255
cols = np.arange(w)
feet = a[int(HH * .92):]
fx = np.where(feet.max(0) > .3)[0]
ax = round(float(((fx.min() + fx.max()) / 2 + (a * cols).sum() / a.sum()) / 2), 1)
top = a[:int(HH * .2)]
hx = float((top * cols).sum() / max(top.sum(), 1))
hxl = round(max(0, min(w - HEAD, hx - HEAD / 2)), 1)

if x + w > cuts.width:
    yF = cuts.height + 4
    yU, yL = yF + HH + 2, yF + HH + 2 + 146 + 2
    x = 0
    print('started a new sheet band at y', yF)

# The three slices stack below each other, so the band needs room for all of
# them -- not just the full-height one. Without this the upper and lower slices
# paste past the bottom edge, PIL drops them silently, and the fighter's tile
# looks right (it uses `full`) while the game draws nothing: drawCut composes
# the body from `upper` and `lower`.
need = yL + 138 + 2
if need > cuts.height:
    grown = Image.new('RGBA', (cuts.width, need), (0, 0, 0, 0))
    grown.paste(cuts, (0, 0))
    cuts = grown
    print('grew the atlas %d -> %d so the band fits' % (atlas_h0, need))

old = cm['chars'][cid]
base = len(F)
for yy, sl in ((yF, (0, HH)), (yU, (0, 146)), (yL, (HIP, HH))):
    cuts.paste(im.crop((0, sl[0], w, sl[1])), (x, yy))
    F.append([x, yy, w, sl[1] - sl[0]])
cm['chars'][cid] = {'full': base, 'upper': base + 1, 'lower': base + 2, 'hip': HIP,
                    'ax': ax, 'h': HH, 'w': w, 'scale': old.get('scale', 0.7692307692307692),
                    'head': [hxl, 0, HEAD, HEAD]}
print(f'{cid}: frames {old["full"]}..{old["full"]+2} -> {base}..{base+2}  '
      f'w {old["w"]} -> {w}  ax {old["ax"]} -> {ax}  room left {cuts.width - x - w}')

b = io.BytesIO()
cuts.save(b, 'WEBP', quality=94, method=6)
cd = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
nl = line.replace('"cuts":"' + A['cuts'] + '"', '"cuts":"' + cd + '"', 1)
nl = nl.replace('"cutsMeta":' + json.dumps(orig_meta, separators=(',', ':')),
                '"cutsMeta":' + json.dumps(cm, separators=(',', ':')), 1)
assert f'"{cid}":' in nl and cd in nl and A['cutsN'] in nl
open(HTML, 'w', encoding='utf-8').write(s[:i] + nl + s[j:])
print('size', len(open(HTML, encoding='utf-8').read().encode()))
