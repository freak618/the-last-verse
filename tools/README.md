# Sprite pipeline

Turns a set of AI-made sheets into one packed sprite sheet the game can load.
Not part of the shipped game — the itch workflow skips this folder.

## Sheets

Three source sheets per fighter, each a 4-column grid:

| sheet | rows |
|---|---|
| `A` | idle, walk, jump, block |
| `B` | punch, kick, special, ultra |
| `C` | hit, knockdown, victory |

## Order

1. **`greenscreen_key.py`** — only for a sheet that arrives on a flat backdrop.
   Keys on *distance to the backdrop colour* rather than on green dominance,
   and keeps only border-connected background, so a green flame or a green orb
   is never mistaken for the backdrop. Writes the sheet out on magenta.
2. **`regrid2.py`** — re-lays each sheet onto a clean 4-column grid of 256px
   cells. Reads `rawA.png` / `rawB.png` / `rawC.png` from the working directory.
3. **ESR upscale** each `X.jpg` to `X_hd.png`, then resize to 2048 wide.
4. **`cut.py`** — cuts every frame and packs `sheet.png` + `sheet.json`.
5. `integrate.py <id> sheet.png sheet.json` embeds it and switches the fighter
   from photo cutout to animated sprite.

## Why each sheet gets its own scale

Source sheets are not drawn at one pixel density: a 1600px attack sheet and a
1024px movement sheet put the same character at very different pixel sizes. One
shared pixel scale across all three therefore makes the character a *different
size per sheet* — which is what made Mordemir attack a head taller than he
walked.

`regrid2.py` normalises on the character instead. Each sheet is scaled so its
typical standing figure is the same height, measured with an interquartile mean
so a kick, a flame aura or a knockdown cannot drag a sheet's measure around.

## Checking a cut

Two numbers catch almost everything:

- **Alpha coverage** — compare each frame's opaque-pixel count against its row
  median; under 45% means the key ate part of the figure (`knockdown` is
  legitimately smaller, so exclude it).
- **Height spread** — group frame heights by animation. Movement, attack and
  hurt rows should *interleave*. If the attack rows sit entirely above the
  movement rows, the per-sheet scale is wrong.
