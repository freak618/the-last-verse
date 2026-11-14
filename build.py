#!/usr/bin/env python3
"""Build a publishable copy of The Last Verse from the single source file.

  build.py OUTDIR [--nomusic] [--lean]

Takes /home/claude/lastverse.html (the one source of truth, with art inlined
as base64) and emits:
    OUTDIR/index.html          page with art swapped for relative paths
    OUTDIR/assets/<key>.<ext>  each inlined blob written out as a real file
plus sheets/, stages/, sfx/, media/ and (unless --nomusic) music/ copied
from the repo.

--nomusic empties the TRACKS list, so the jukebox goes inert and the build
needs no music/ files at all. Every jukebox entry point already guards on
`!TRACKS.length`, so nothing else has to change.

--lean cuts the build down to a workbench: a handful of fighters and three
stages, enough to build and test a new character or a new level against,
and nothing else. It trims the arrays at runtime rather than editing them,
so it keeps working untouched as the source grows.
"""
import base64
import glob
import hashlib
import hashlib, os, re, shutil, sys

SRC = '/home/claude/lastverse.html'
REPO = '/home/claude/the-last-verse'
CHURN = {'cuts', 'atlas'}   # art that is rewritten as the roster changes

# The workbench roster: the most recently built fighters, so the sprite
# pipeline has fresh reference points, plus a few different body types.
DEV_ROSTER = ['mizzmurda', 'nicky6', 'zactyrr', 'otice', 'marshall',
              'preach', 'dabbalette', 'pow', 'freakyp', '1eye']
# One stage per floor-rendering path, so a new stage can be checked against
# any of them: the legacy mirrored floor, the row-by-row renderer reading a
# separate painting, and the only stage that still carries props.
DEV_STAGES = ['pops', 'carnival', 'gathering']

TRIM = '''
/* dev workbench build: only a few fighters and stages, so there is room to
   add new ones. Fighters without a sheet (coming soon) and your own custom
   fighters are left alone. Trimmed here rather than in the arrays above so
   this keeps working as the roster grows. */
(()=>{const KC=new Set(%s),KS=new Set(%s);
  for(let i=CHARS.length-1;i>=0;i--){const c=CHARS[i];if((c.sheet||c.sprite)&&!KC.has(c.id))CHARS.splice(i,1)}
  for(let i=STAGES.length-1;i>=0;i--)if(!KS.has(STAGES[i].id))STAGES.splice(i,1)})();
'''


def array_end(html, name):
    """Index just past the `];` that closes `const <name>=[`."""
    i = html.index('const %s=[' % name)
    j = html.index('\n];', i)
    return j + 3


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[1]
    flags = sys.argv[2:]
    nomusic, lean = '--nomusic' in flags, '--lean' in flags
    os.makedirs(os.path.join(out, 'assets'), exist_ok=True)

    html = open(SRC, encoding='utf-8').read()

    # which stage paintings ship as their own files rather than inline
    stage_files = dict(re.findall(r"(\w+):'(jg_\w+)'",
                                  re.search(r'const STAGE_FILES=\{([^}]*)\}', html).group(1)))

    keep_assets = None
    if lean:
        # drop the stages we are not keeping before their images load
        kept_sf = {k: v for k, v in stage_files.items() if k in DEV_STAGES}
        html = re.sub(r'const STAGE_FILES=\{[^}]*\}',
                      'const STAGE_FILES=' + ('{%s}' % ','.join(
                          "%s:'%s'" % (k, v) for k, v in kept_sf.items())), html, count=1)
        stage_files = kept_sf
        # inline paintings are kept only for the stages that survive
        keep_assets = {'atlas', 'atlasN', 'cuts', 'cutsN', 'mature'} | (set(DEV_STAGES) - set(kept_sf))
        end = array_end(html, 'STAGES')
        html = html[:end] + (TRIM % (DEV_ROSTER, DEV_STAGES)) + html[end:]

    wrote, skipped = [], 0

    def swap(m):
        nonlocal skipped
        key, ext, data = m.group(1), m.group(2), m.group(3)
        path = 'assets/%s.%s' % (key, ext)
        if keep_assets is not None and key not in keep_assets:
            skipped += 1
            return '"%s":""' % key          # never referenced once the stage is gone
        raw = base64.b64decode(data)
        # cuts.webp and atlas.webp change whenever art changes but keep their
        # name, so a browser that cached an older copy keeps drawing it and new
        # portraits look like they never shipped -- an empty square where the
        # page expects art. Putting the content hash in the FILENAME makes every
        # change a new URL, which no cache can get wrong. A query string would
        # be tidier, but not every host resolves a path that carries one.
        if key in CHURN:
            path = 'assets/%s-%s.%s' % (key, hashlib.sha256(raw).hexdigest()[:8], ext)
            for stale in glob.glob(os.path.join(out, 'assets', '%s-*.%s' % (key, ext))):
                if os.path.basename(stale) != os.path.basename(path):
                    os.remove(stale)
        with open(os.path.join(out, path), 'wb') as f:
            f.write(raw)
        wrote.append(path)
        return '"%s":"%s"' % (key, path)

    html = re.sub(r'"([A-Za-z0-9_]{1,40})"\s*:\s*"data:image/(\w+);base64,([A-Za-z0-9+/=]*)"',
                  swap, html)
    if re.search(r'data:image/\w+;base64', html):
        sys.exit('ERROR: base64 image left in page after swap')

    if nomusic:
        html, n = re.subn(r'const TRACKS=\[.*?\n\];',
                          'const TRACKS=[];/* music lives in the itch.io build only */',
                          html, count=1, flags=re.S)
        if n != 1:
            sys.exit('ERROR: could not find the TRACKS list to empty')
        # name the dev build apart from the release so the two artifacts are
        # tellable at a glance (the <title> tag is what names an artifact)
        html = html.replace('<title>The Last Verse</title>',
                            '<title>Last Verse Dev Build</title>', 1)

    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)

    # --- everything that ships beside the page -----------------------------
    def copy(sub, names=None):
        src_dir = os.path.join(REPO, sub)
        if not os.path.isdir(src_dir):
            return 0, 0
        dst = os.path.join(out, sub)
        os.makedirs(dst, exist_ok=True)
        n = b = 0
        fresh = set()
        for f in sorted(os.listdir(src_dir)):
            if names is not None and os.path.splitext(f)[0] not in names:
                continue
            shutil.copy2(os.path.join(src_dir, f), os.path.join(dst, f))
            fresh.add(f)
            n += 1
            b += os.path.getsize(os.path.join(dst, f))
        # Drop whatever this build did not write. Copying without pruning leaves
        # a stale output directory that every check still passes -- the page is
        # correct and nothing it references is missing -- so the dead files ride
        # silently into the zips. Two removed stage paintings shipped that way.
        for f in os.listdir(dst):
            if f not in fresh:
                os.remove(os.path.join(dst, f))
                print('  pruned %s/%s (no longer part of the build)' % (sub, f))
        return n, b

    rows = []
    page = os.path.getsize(os.path.join(out, 'index.html'))
    art = sum(os.path.getsize(os.path.join(out, p)) for p in wrote)
    rows.append(('index.html', 1, page))
    rows.append(('assets/', len(wrote), art))
    rows.append(('sheets/', *copy('sheets', set(DEV_ROSTER) if lean else None)))
    rows.append(('stages/', *copy('stages', set(stage_files.values()) if lean else None)))
    rows.append(('sfx/', *copy('sfx')))
    rows.append(('media/', *copy('media')))
    if not nomusic:
        rows.append(('music/', *copy('music')))

    print('%-12s %5s %10s' % ('', 'files', 'size'))
    for name, n, b in rows:
        print('%-12s %5d %9.2f MB' % (name, n, b / 1048576))
    tn = sum(r[1] for r in rows)
    tb = sum(r[2] for r in rows)
    print('%-12s %5d %9.2f MB   of 511 files / 256 MB' % ('TOTAL', tn, tb / 1048576))
    print('\nmusic %s%s' % ('OFF (TRACKS emptied)' if nomusic else 'on',
                            '   ·   lean: %d fighters, %d stages, %d paintings dropped'
                            % (len(DEV_ROSTER), len(DEV_STAGES), skipped) if lean else ''))

    # A build that only counts files cannot tell that one it references is
    # absent, or that a portrait points at empty atlas pixels. Both have
    # shipped. The lean build drops fighters and stages on purpose, so it is
    # checked for blank portraits but not for every referenced path.
    import subprocess
    print()
    v = subprocess.run(['python3', '-I', f'{REPO}/tools/verify.py', out]
                       + (['--lean'] if lean else []), capture_output=True, text=True)
    print(v.stdout.rstrip() or v.stderr.rstrip())
    if v.returncode:
        raise SystemExit('build is incomplete -- see above')


main()
