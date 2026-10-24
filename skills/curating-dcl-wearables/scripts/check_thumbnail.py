#!/usr/bin/env python3
"""Check a wearable/emote thumbnail before upload.

usage: python3 check_thumbnail.py thumb.png [--item item_render.png]

Hard rules (FAIL): PNG, square, <= 1024 px, <= 1 MB, transparent background (>= 90% of the outermost pixel ring
transparent, alpha <= 8: the same test as Decentraland's wearable-validator).
Curation guidance (WARN): 256 px is what the docs ask for; the item alone, filling the frame; nothing but the item,
except an optional small logo pinned to a corner, preferably bottom right. Separate opaque blobs are reported with
their position so a stray graphic, text or off-corner logo is easy to spot. Needs Pillow + numpy.
"""
import argparse, os, sys
import numpy as np
from PIL import Image

ALPHA = 8          # wearable-validator manifest.thumbnail.alphaThreshold
BORDER = 0.9       # wearable-validator manifest.thumbnail.minTransparentBorderRatio


def components(mask, min_px):
    """Connected opaque regions (4-neighbour) as (pixel count, (x0, y0, x1, y1)), largest first."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, n, box = [(y0, x0)], 0, [x0, y0, x0, y0]
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            n += 1
            box = [min(box[0], x), min(box[1], y), max(box[2], x), max(box[3], y)]
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        if n >= min_px:
            out.append((n, tuple(box)))
    return sorted(out, reverse=True)


def where(box, size):
    cx, cy = (box[0] + box[2]) / 2 / size, (box[1] + box[3]) / 2 / size
    col = 'left' if cx < 1 / 3 else 'right' if cx > 2 / 3 else 'centre'
    row = 'top' if cy < 1 / 3 else 'bottom' if cy > 2 / 3 else 'middle'
    return f'{row}-{col}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('png')
    a = ap.parse_args()
    rows, worst = [], 0
    def add(level, label, value, rule=''):
        nonlocal worst
        rows.append((level, label, value, rule))
        worst = max(worst, {'PASS': 0, 'INFO': 0, 'WARN': 1, 'FAIL': 2}[level])

    raw = open(a.png, 'rb').read()
    add('PASS' if raw[:8] == b'\x89PNG\r\n\x1a\n' else 'FAIL', 'format', 'PNG' if raw[:4] == b'\x89PNG' else 'not PNG')
    size = len(raw)
    add('FAIL' if size > 1048576 else 'PASS', 'file size', f'{size / 1024:.0f} KB', '<= 1 MB')
    im = Image.open(a.png)
    w, h = im.size
    add('FAIL' if w != h else 'PASS', 'square', f'{w}x{h}')
    add('FAIL' if max(w, h) > 1024 else 'WARN' if w != 256 else 'PASS', 'size', f'{w}x{h}',
        '<= 1024 (validator); docs ask for 256 px')
    rgba = np.asarray(im.convert('RGBA'))
    alpha = rgba[:, :, 3]
    ring = np.concatenate([alpha[0], alpha[-1], alpha[1:-1, 0], alpha[1:-1, -1]])
    ratio = float((ring <= ALPHA).mean())
    add('FAIL' if ratio < BORDER else 'PASS', 'transparent background', f'{ratio * 100:.0f}% of border clear', '>= 90%')

    # Composition, judged on a 256 px copy.
    small = np.asarray(im.convert('RGBA').resize((256, 256), Image.NEAREST))[:, :, 3] > 32
    blobs = components(small, min_px=12)
    if not blobs:
        add('FAIL', 'content', 'image is empty')
    else:
        # Blobs at least a quarter the size of the largest are parts of the item (a pair of shoes, hands + prop).
        parts = [b for b in blobs if b[0] >= blobs[0][0] * 0.25]
        extra = [b for b in blobs if b[0] < blobs[0][0] * 0.25]
        box = (min(b[1][0] for b in parts), min(b[1][1] for b in parts), max(b[1][2] for b in parts), max(b[1][3] for b in parts))
        fill = max(box[2] - box[0], box[3] - box[1]) / 256
        add('WARN' if fill < 0.6 else 'PASS', 'item fills the frame', f'{fill * 100:.0f}% of the longer side', '>= 60%')
        for n2, b2 in extra[:6]:
            pos = where(b2, 256)
            corner = pos in ('bottom-right', 'bottom-left', 'top-right', 'top-left')
            outside = b2[0] > box[2] or b2[2] < box[0] or b2[1] > box[3] or b2[3] < box[1]
            if not outside and not corner:
                continue   # a small detail inside the item's own area (a buckle, a tag)
            if corner:
                level = 'INFO' if pos == 'bottom-right' else 'WARN'
                note = 'corner element (logo?): keep it small' + ('' if pos == 'bottom-right' else '; bottom right is preferred')
            else:
                level, note = 'WARN', 'separate graphic: only the item, plus at most a small corner logo'
            add(level, f'separate element at {pos}', f'{n2} px, {b2[2] - b2[0] + 1}x{b2[3] - b2[1] + 1}', note)
        if len(extra) > 6:
            add('WARN', 'many separate elements', len(extra), 'thumbnails should be simple: the item alone')
        add('INFO', 'look at it yourself', 'simple? item recognisable? matches the model?',
            'curators also reject thumbnails that misrepresent the item')

    print(os.path.basename(a.png))
    for level, label, value, rule in rows:
        print(f'  {level:<4}  {label:<34} {str(value):<34} {rule}')
    print({0: 'NO WARNINGS', 1: 'WARNINGS', 2: 'SOME FAILED'}[worst])
    sys.exit(1 if worst == 2 else 0)


if __name__ == '__main__':
    main()
