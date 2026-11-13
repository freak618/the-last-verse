# Sprite pipeline

Turns a set of AI-made sheets into one packed sprite sheet the game can load.
Not part of the shipped game — the itch workflow skips this folder.

## Sheets

Three source sheets per fighter, each a 4-column grid, named `A_src` / `B_src` /
`C_src`:

| sheet | rows |
|---|---|
| `A` | idle, walk, jump, block |
| `B` | punch, kick, special, ultra |
| `C` | hit, knockdown, victory |

## Order

1. **`degrid.py`** — only for a sheet that ships with its cell borders painted
   on. Finds whole dark rows and columns and fills them from the nearest clean
   line either side.
2. **`prep.py`** — lifts each sheet off its backdrop into a real alpha channel.
   Writes `rawA.png` / `rawB.png` / `rawC.png` as RGBA.
3. **`regrid2.py`** — re-lays each sheet onto a clean 4-column grid of 256px
   cells, carrying alpha. Writes `X.png` (RGBA), plus `X.jpg` and
   `X_alpha.png` for the upscaler.
4. **`upscale.py`** — upscales to 2048 wide and recombines colour with alpha.
5. **`cut.py`** → `cut2z.py` — cuts every frame and packs `sheet.png` +
   `sheet.json`.
6. `integrate.py <id> sheet.png sheet.json` embeds it and switches the fighter
   from photo cutout to animated sprite.

## Alpha travels; nothing downstream re-keys

The pipeline used to cut on a key colour at every stage, which forces the key to
be a hue the character's art does not contain. There is no such hue. Mordemir's
flame is green. Devilette's energy was purple, then cyan and pink, and her
sparks are gold. Keying green cost 24% of her cyan aura; keying magenta cost 9%
of her pink projectile.

So the backdrop comes off **once**, in `prep.py`, and the alpha goes with the art
from then on. `cut2z.py` uses a real alpha channel when it finds one and only
falls back to its old `LV_KEY` colour key for sheets built before this.

### Getting the alpha right

A backdrop screen contaminates everything drawn over it, so a soft glow really
is part backdrop and belongs at part alpha.

- **Measure how far a pixel leans toward the backdrop's hue.** That puts a
  glow at partial alpha, which is correct, and the same pass removes the lean
  from the colour (despill) so the glow keeps its own hue.
- **Do not measure distance to the backdrop colour.** It calls a green-blended
  glow fully opaque and leaves it green — Devilette's cyan aura came back as a
  green blob.

The backdrop colour is the single most common colour in the image. Never sample
it from the border: a sheet's own grid lines sit exactly there, and a skewed
backdrop colour made 93% of one sheet read as figure.

`--keep-enclosed` is for art that contains the backdrop's own hue, where a gap
between limbs cannot be told from an effect. It keeps every region the figure
encloses, at the cost of leaving backdrop in those gaps. Mordemir needs it; most
characters do not.

## Why each sheet gets its own scale

Source sheets are not drawn at one pixel density: a 1600px attack sheet and a
1024px movement sheet put the same character at very different pixel sizes. One
shared pixel scale across all three therefore makes the character a *different
size per sheet* — which is what made Mordemir attack a head taller than he
walked.

`regrid2.py` normalises on the character instead. Each sheet is scaled so its
typical standing figure is the same height, measured with an interquartile mean
so a kick, a flame aura or a knockdown cannot drag a sheet's measure around.

## Rows are split on a quiet line, and limbs cross it

`regrid2.py` separates the source rows along the quietest horizontal line it can
find in each band. A figure that reaches past that line gets severed by it --
Vanitylette's uppercut raises a fist into the row above.

A severed piece attaches to the figure on the other side of the split line that
it lines up with horizontally, not to whichever figure is nearest by bounding
box. Nearest-by-box put her fist on her projectile frame one row up, which left
a disembodied flaming fist floating under her *and* an uppercut with no fist on
it -- two broken frames from one bad attachment.

## Checking a cut

Three checks catch nearly everything:

- **Alpha coverage** — compare each frame's opaque-pixel count against its row
  median; under 45% means the key ate part of the figure (`knockdown` is
  legitimately smaller, so exclude it).
- **Height spread** — group frame heights by animation. Movement, attack and
  hurt rows should *interleave*. If the attack rows sit entirely above the
  movement rows, the per-sheet scale is wrong. If one animation's frames are
  all an identical height well under the others, they are being clipped — a
  staggered source sheet spilling into the band below does this.
- **Render every frame and look at it.** Coverage and height are blind to a
  hue that came out wrong and to art landing in the wrong frame. A green fringe,
  a recoloured glow, a stray fist under a fighter and a missing one above her
  are all obvious by eye and all passed both numeric checks clean.
