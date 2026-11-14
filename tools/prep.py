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

A NEUTRAL backdrop -- black, white, or any grey -- takes a different path,
chosen automatically when the modal colour's channels sit within NEUTRAL_SPREAD
of each other. Leaning is meaningless there: grey leans nowhere, so there is no
hue to measure against. A black hoodie on black, or white sneakers on white,
is separated only by the outline the art draws around the figure. So the
backdrop is filled inward from the border and everything the outline encloses
is kept, which is what --keep-enclosed does for a coloured screen, except that
here it is the rule rather than the exception. Outside that silhouette, alpha
follows distance from the backdrop, so a glow that spills past the outline
fades out instead of ending at it. Nothing is despilled: a neutral screen
contaminates by lightening or darkening, and neither can be undone.

Writes raw<sheet>.png as RGBA.
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

LO, HI = 28, 95          # leaning below LO is fully opaque, above HI fully clear
DESPILL = 0.15           # fraction of the backdrop-hue excess left behind
NEUTRAL_SPREAD = 20      # modal channels this close together mean no hue to lean on
NEAR_BG = 40             # an enclosed pixel this close to the screen colour IS screen
NEUTRAL_LO, NEUTRAL_HI = 8, 60   # distance ramp for art that spills past the outline


def prep_neutral(f, bg):
    """Alpha for a backdrop with no hue: the outline encloses the figure, and
    distance from the backdrop carries whatever escapes it."""
    dist = np.abs(f - bg.astype(np.float32)).max(axis=2)
    flat = dist <= NEUTRAL_LO
    lab, _ = ndimage.label(flat)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(edge))             # backdrop the border can reach
    spill = np.clip((dist - NEUTRAL_LO) / (NEUTRAL_HI - NEUTRAL_LO), 0, 1)
    return np.maximum((~outside).astype(np.float32), spill), int((~outside).sum())


def prep(src, out, keep_enclosed=False, bleed=14):
    f = np.array(Image.open(src).convert('RGB')).astype(np.float32)
    cols, counts = np.unique(f.astype(np.int16).reshape(-1, 3), axis=0, return_counts=True)
    bg = cols[counts.argmax()]
    neutral = bool(bg.max() - bg.min() <= NEUTRAL_SPREAD)
    dom = int(np.argmax(bg))                      # which channel the screen is
    others = [c for c in range(3) if c != dom]

    if neutral:
        alpha, enclosed_n = prep_neutral(f, bg)
    else:
        orig = f.copy()
        rest = np.maximum(f[..., others[0]], f[..., others[1]])
        lean = f[..., dom] - rest
        alpha = 1 - np.clip((lean - LO) / (HI - LO), 0, 1)

        # Despill: pull the screen's channel back down toward the other two.
        f[..., dom] = np.where(lean > 0, rest + lean * DESPILL, f[..., dom])

    clear = alpha < 0.5
    if not neutral:
        lab, _ = ndimage.label(clear)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        enclosed = clear & ~np.isin(lab, list(edge))
        enclosed_n = int(enclosed.sum())
        if keep_enclosed:
            # Keep only the enclosed pixels that are not the screen's own colour.
            # "Enclosed" catches two different things at once: the character's
            # green trim, which must be kept, and real screen trapped between an
            # arm and a body, which must not. Keeping the lot put a slab of flat
            # green under Blynd's arm. Colour distance separates them easily --
            # his trim is a dark yellow-green, the screen is saturated.
            own = enclosed & (np.abs(orig - bg).max(axis=2) > NEAR_BG)
            enclosed_n = int(own.sum())
            # Restoring alpha is only half of it. Keeping a pixel means calling
            # it figure, so it was never contaminated -- take its colour back
            # too. Without this Blynd's trim came back opaque but despilled to a
            # dull olive, which reads pink over the stage.
            alpha[own] = 1.0
            f[own] = orig[own]

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
    how = 'NEUTRAL, filled from the border' if neutral else f'channel "{"RGB"[dom]}"'
    kept = 'enclosed by the outline' if neutral else ('kept' if keep_enclosed else 'cleared')
    print(f'{src.split("/")[-1]}: screen {bg.astype(int).tolist()} {how}  '
          f'art {100*solid.mean():.1f}%  soft {100*soft:.1f}%  {enclosed_n} px {kept}')


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    keep = '--keep-enclosed' in sys.argv
    for k in 'ABC':
        prep(f'{d}/{k}_src.webp', f'{d}/raw{k}.png', keep_enclosed=keep)
