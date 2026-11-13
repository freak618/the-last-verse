"""Cut AI sprite sheets (green screen, 4-column grids) into a trimmed atlas the game loads."""
import sys, json, numpy as np, cv2
from skimage.segmentation import watershed
from PIL import Image

LAYOUT = {  # sheet -> rows (animation names the game's importer understands)
    'A': ['idle', 'walk', 'jump', 'block'],
    'B': ['punch', 'kick', 'special', 'ultra'],
    'C': ['hit', 'knockdown', 'victory'],
}

def key_green(rgb):
    f = rgb.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    spill = np.minimum(r, b) - g
    a = 1 - np.clip((spill - 28) / (95 - 28), 0, 1)          # strong green -> transparent
    # despill: pull leftover green on edges back to neutral
    mx = np.minimum(r, b)
    # only despill near the cut edge, so green inside the art (shirt print) keeps its colour
    edge = cv2.dilate(((a < 0.98)).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    r2 = np.where(edge & (r > g), g + (r - g) * 0.15, r)
    b2 = np.where(edge & (b > g), g + (b - g) * 0.15, b)
    out = np.stack([r2, g, b2], -1)
    return out.clip(0, 255).astype(np.uint8), (a * 255).astype(np.uint8)

def clean(alpha, min_area):
    m = (alpha > 40).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1: return alpha
    big = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    keep = np.zeros(n, bool); keep[big] = True
    for q in range(1, n):
        if st[q, cv2.CC_STAT_AREA] >= min_area: keep[q] = True   # sparks and energy blasts survive, specks don't
    mask = keep[cc]
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return np.where(mask, alpha, 0).astype(np.uint8)

def cut(sheets, out_png, out_json, name, scale_note=1):
    frames, anims, items = {}, {}, []
    for sid, path in sheets.items():
        im = np.asarray(Image.open(path).convert('RGB'))
        H, W = im.shape[:2]; rows = LAYOUT[sid]; cw, ch = W / 4, H / len(rows)
        rgb, al = key_green(im)
        # every connected piece of art goes to the cell holding most of it, so limbs that cross a cell edge stay attached
        m = (al > 150).astype(np.uint8)   # solid art only; soft glows are added back per piece below
        n, cc, st, cen = cv2.connectedComponentsWithStats(m, 8)
        cell_of = {}
        # a piece bigger than a cell means two frames touch: split it on the grid lines
        nxt = n
        for q in range(1, n):
            if st[q, 3] > ch * 1.12 or st[q, 2] > cw * 1.12:
                yy, xx = np.nonzero(cc == q); cells = (np.clip(yy // ch, 0, len(rows) - 1) * 4 + np.clip(xx // cw, 0, 3)).astype(int)
                ks, cnt = np.unique(cells, return_counts=True)
                if (cnt >= cnt.max() * .5).sum() < 2: continue          # only small tips cross the line: keep it whole
                # two whole frames touch: split where they meet (the narrowest neck), not on the grid line
                x0q, y0q, wq, hq = st[q, :4]; comp = (cc[y0q:y0q + hq, x0q:x0q + wq] == q).astype(np.uint8)
                seeds = None
                for it in range(1, 40):
                    er = cv2.erode(comp, np.ones((3, 3), np.uint8), iterations=it)
                    sn, sl, ss, _ = cv2.connectedComponentsWithStats(er, 8)
                    big = [k for k in range(1, sn) if ss[k, 4] >= comp.sum() * .03]
                    if len(big) >= 2: seeds = np.where(np.isin(sl, big), sl, 0); break
                    if sn <= 1: break
                if seeds is not None:
                    dist = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
                    ws = watershed(-dist, seeds, mask=comp.astype(bool))
                    for k in np.unique(ws[ws > 0]):
                        sub = np.zeros_like(cc, bool); sub[y0q:y0q + hq, x0q:x0q + wq] = ws == k
                        cc[sub] = nxt; nxt += 1
                    continue
                main = ks[cnt.argmax()]
                for k, c in zip(ks, cnt):
                    if c < cnt.max() * .2: cells[cells == k] = main         # tips ride along with the biggest part
                for k in np.unique(cells):
                    sel = cells == k; cc[yy[sel], xx[sel]] = nxt; nxt += 1
        n = nxt; st = np.zeros((n, 5), int)
        for q in range(1, n):
            yy, xx = np.nonzero(cc == q)
            if len(yy): st[q] = [xx.min(), yy.min(), xx.max() - xx.min() + 1, yy.max() - yy.min() + 1, len(yy)]
        for q in range(1, n):
            if st[q, 4] < cw * ch * .002: continue          # specks
            ys, xs = np.nonzero(cc[st[q, 1]:st[q, 1] + st[q, 3], st[q, 0]:st[q, 0] + st[q, 2]] == q)
            ci_ = np.clip(((xs + st[q, 0]) // cw).astype(int), 0, 3); ri_ = np.clip(((ys + st[q, 1]) // ch).astype(int), 0, len(rows) - 1)
            k = np.bincount(ri_ * 4 + ci_, minlength=4 * len(rows)).argmax()
            cell_of.setdefault(int(k), []).append(q)
        for ri, anim in enumerate(rows):
            anims.setdefault(anim, [])
            for ci in range(4):
                qs = cell_of.get(ri * 4 + ci)
                if not qs: continue
                core = np.isin(cc, qs).astype(np.uint8)
                g = max(3, int(cw * .035)) | 1
                mask = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (g, g))).astype(bool) & (al > 12)
                # loose bits below the fighter's feet belong to the frame underneath: drop them
                pn, pc, ps, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
                if pn > 2:
                    mainq = 1 + np.argmax(ps[1:, 4]); foot = ps[mainq, 1] + ps[mainq, 3]
                    for q2 in range(1, pn):
                        if q2 == mainq: continue
                        top = ps[mainq, 1]; cy = ps[q2, 1] + ps[q2, 3] / 2; tiny = ps[q2, 4] < ps[mainq, 4] * .006
                        if ps[q2, 1] > foot - ch * .04 or (tiny and (cy > foot - ch * .1 or cy < top + ch * .03)): mask[pc == q2] = False
                ys, xs = np.nonzero(mask & (al > 12))
                bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
                a = np.where(mask, al, 0)[by0:by1, bx0:bx1]
                rgba = np.dstack([rgb[by0:by1, bx0:bx1], a])
                # anchor: hips at the cell's horizontal centre, feet at the frame's lowest pixel
                ax = (ci + .5) * cw - bx0; ay = by1 - by0
                items.append((anim, ci, Image.fromarray(rgba.astype(np.uint8), 'RGBA'), ax, ay))
    # pack: one animation per row
    order = ['idle', 'walk', 'jump', 'block', 'punch', 'kick', 'special', 'ultra', 'hit', 'knockdown', 'victory']
    pad = 2; x = y = pad; rowh = 0; Wmax = 0; place = []
    for anim in order:
        fr = [t for t in items if t[0] == anim]
        if not fr: continue
        if anim == 'block' and len(fr) == 4: fr = [fr[1], fr[2], fr[0], fr[3]]  # the game holds frame 0 while blocking: use the full guard
        x = pad
        for t in fr:
            w, h = t[2].size; place.append((t, x, y)); x += w + pad; rowh = max(rowh, h); Wmax = max(Wmax, x)
        y += rowh + pad; rowh = 0
    sheet = Image.new('RGBA', (Wmax, y), (0, 0, 0, 0))
    for (anim, ci, img, ax, ay), px, py in place:
        sheet.paste(img, (px, py))
        k = f'{name}_{anim}_{ci}'
        frames[k] = {'frame': {'x': px, 'y': py, 'w': img.width, 'h': img.height}, 'anchor': {'x': round(float(ax), 1), 'y': round(float(ay), 1)},
                     'root': {'x': round(float(ax), 1), 'y': round(float(ay), 1)}}
        anims.setdefault(anim, []).append(k)
    anims = {k: v for k, v in anims.items() if v}
    idle0 = frames[anims['idle'][0]]['frame']
    meta = {'app': 'Last Verse AI sheet cutter', 'image': out_png.split('/')[-1], 'size': {'w': sheet.width, 'h': sheet.height},
            'charHeight': idle0['h'], 'rate': 0, 'facing': 'right'}
    sheet.save(out_png, optimize=True)
    json.dump({'frames': frames, 'animations': anims, 'meta': meta}, open(out_json, 'w'), indent=1)
    return sheet, frames, anims, meta

if __name__ == '__main__':
    d, name, suf = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''
    s, f, a, m = cut({k: f'{d}/{k}{suf}' for k in 'ABC'}, f'{d}/{name}-sheet.png', f'{d}/{name}-sheet.json', name)
    print(s.size, {k: len(v) for k, v in a.items()}, m['charHeight'])
