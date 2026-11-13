"""Check a built game folder is actually complete before it ships.

Twice now a build has gone out missing a file it references, and neither time
did anything complain -- the page just drew nothing where the art should be:

  * assets/ was never tracked in the repo at all, so every photo-cutout fighter
    and 13 stage paintings were missing from GitHub Pages and itch.
  * A new fighter's portrait went into assets/cuts.webp, but only her sprite
    sheet was shipped, so her select-screen tile was blank.

Both are invisible to a build that only reports file counts, and both are caught
by the two checks here: every path the page asks for exists, and every portrait
the atlas promises actually has pixels in it.

    python3 -I verify.py <built folder>
"""
import json
import os
import re
import sys
import numpy as np
from PIL import Image

d = sys.argv[1] if len(sys.argv) > 1 else '.'
# The lean dev build keeps the full page but ships only a few fighters and
# stages, so most referenced paths are absent by design. Its portraits are
# still checked -- the atlas is shipped whole either way.
lean = '--lean' in sys.argv
html = open(f'{d}/index.html', encoding='utf-8').read()
fail = []

# 1. every relative path the page loads is present in the folder.
# Comment lines are skipped: the source carries a template song entry and a
# prose note about the hit sounds, and neither names a real file.
refs = set()
for ln in html.split('\n'):
    t = ln.strip()
    if t.startswith('//') or t.startswith('*') or t.startswith('/*'):
        continue
    refs |= set(re.findall(r'["\'(]((?:assets|sheets|stages|music|sfx|media)/[\w./-]+)', ln))
missing = sorted(p for p in refs if not os.path.exists(f'{d}/{p}'))
if lean:
    print(f'referenced files : {len(refs)} referenced, '
          f'{len(missing)} absent by design (lean build)')
else:
    print(f'referenced files : {len(refs)} referenced, {len(missing)} missing')
    if missing:
        fail.append(f'{len(missing)} referenced file(s) missing: {missing[:6]}')

# 2. every cutout the atlas promises has pixels where it says
i = html.index('const ASSET=')
A = json.loads(html[i:html.index('\n', i)][len('const ASSET='):].rstrip(';'))
cm = A['cutsMeta']
blank = []
if not os.path.exists(f'{d}/assets/cuts.webp'):
    print('cutout portraits : atlas file itself is missing')
    fail.append('assets/cuts.webp is missing, so every portrait is blank')
    cm = {'chars': {}}
atlas = (Image.open(f'{d}/assets/cuts.webp').convert('RGBA')
         if cm['chars'] else Image.new('RGBA', (1, 1)))
al = np.asarray(atlas)[..., 3]
for cid, c in cm['chars'].items():
    x, y, w, h = cm['frames'][c['full']]
    if y + h > atlas.height or x + w > atlas.width:
        blank.append((cid, 'outside the atlas'))
    elif (al[y:y + h, x:x + w] > 20).mean() < 0.05:
        blank.append((cid, 'empty'))
print(f'cutout portraits : {len(cm["chars"])} characters, {len(blank)} blank')
if blank:
    fail.append(f'portrait(s) with no art in the atlas: {blank}')

if fail:
    print('\nFAILED')
    for f in fail:
        print(' -', f)
    sys.exit(1)
print('\nOK')
