"""Upscale each regridded sheet to 2048 wide, keeping its alpha intact.

The upscaler takes RGB only, so colour and alpha go up separately and are
recombined here. Colour goes through the model, where invented detail is the
point; alpha goes through Lanczos, where it is not -- a hallucinated edge on a
mask shows up as a chewed outline.
"""
import os
import subprocess
import sys
import numpy as np
from PIL import Image

ESR = '/tmp/claude-0/esr/esr.py'
WEIGHTS = '/tmp/claude-0/esr/general.pth'
WIDTH = 2048


def upscale(d, sheet):
    rgb_in, rgb_hd = f'{d}/{sheet}.jpg', f'{d}/{sheet}_hd.png'
    subprocess.run(['python3', '-I', ESR, rgb_in, rgb_hd, WEIGHTS],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    colour = Image.open(rgb_hd).convert('RGB')
    h = round(colour.height * WIDTH / colour.width)
    colour = colour.resize((WIDTH, h), Image.LANCZOS)

    alpha = Image.open(f'{d}/{sheet}_alpha.png').convert('L').resize((WIDTH, h), Image.LANCZOS)
    out = np.dstack([np.asarray(colour), np.asarray(alpha)])
    Image.fromarray(out, 'RGBA').save(rgb_hd)

    a = np.asarray(alpha)
    print(f'{sheet}: {WIDTH}x{h}   art {100*(a>128).mean():.1f}%   '
          f'soft edge {100*(((a>8)&(a<248)).mean()):.1f}%')


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    for k in 'ABC':
        upscale(d, k)
