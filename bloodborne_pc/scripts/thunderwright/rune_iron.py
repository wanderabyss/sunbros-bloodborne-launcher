# SPDX-License-Identifier: GPL-2.0-or-later
"""Thunderwright's rune-iron hammer head: the Kirkhammer's stone block made dark iron, its Healing
Church inscription replaced by Elder Futhark runes inlaid in silver inside a Norse braid frame.
Norse myth's Mjolnir (an iron hammer, Thor's: *Thunraz in Proto-Germanic), not any modern design.

Made from the player's own Kirkhammer textures (ps4_texture.py reads and writes them), the model
the same mesh. The Kirkhammer's parts (wp_a_1031) share one texture set between the sword and the
hammer; the sword's half of it (the top of the UV square, above HEAD_TOP) is left alone, so only
the stone block changes. The material has no emissive map, so the runes are an inlay (bright
albedo, high specular and gloss) rather than a glow.

Texture roles (BB's weapon material): _a albedo (BC1, alpha kept), _n normal (BC1: X in red,
Y in green), _r specular colour (BC1), _s gloss (BC4).

Places are fractions of the UV square, measured on the 2048x1024 normal map, so the same design
lands on every size of every texture (the _l, low-detail set is half size).
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

HEAD_TOP = 292 / 1024           # above: the sword's blade and hilt
# The stone block's two broad faces (the inscribed ones), (left, top, right, bottom).
FACES = [(268 / 2048, 291 / 1024, 605 / 2048, 866 / 1024), (945 / 2048, 291 / 1024, 1290 / 2048, 866 / 1024)]
# Its narrow side face, given a braid band down the middle.
SIDE = (670 / 2048, 300 / 1024, 880 / 2048, 845 / 1024)
DESIGN = (2048, 1024)           # the design is drawn at this size, then fitted to each texture

# Elder Futhark (public domain), each rune as strokes in a box 1 tall and 0.6 wide (y down).
RUNES = {
    'f': [[(0, 0), (0, 1)], [(0, .3), (.55, .02)], [(0, .55), (.55, .27)]],
    'u': [[(0, 1), (0, 0), (.55, .3), (.55, 1)]],
    'th': [[(0, 0), (0, 1)], [(0, .25), (.5, .5), (0, .75)]],
    'a': [[(0, 0), (0, 1)], [(0, 0), (.5, .25)], [(0, .3), (.5, .55)]],
    'r': [[(0, 0), (0, 1)], [(0, 0), (.5, .22), (0, .45), (.5, 1)]],
    'k': [[(.45, 0), (0, .25), (.45, .5)]],
    'g': [[(0, 0), (.6, 1)], [(.6, 0), (0, 1)]],
    'w': [[(0, 0), (0, 1)], [(0, 0), (.5, .2), (0, .4)]],
    'h': [[(0, 0), (0, 1)], [(.55, 0), (.55, 1)], [(0, .35), (.55, .65)]],
    'n': [[(.3, 0), (.3, 1)], [(.05, .35), (.55, .6)]],
    'i': [[(.3, 0), (.3, 1)]],
    'j': [[(.28, .05), (0, .3), (.28, .55)], [(.32, .45), (.6, .7), (.32, .95)]],
    'ei': [[(.3, 0), (.3, 1)], [(.3, 0), (.6, .22)], [(.3, 1), (0, .78)]],
    'p': [[(0, 0), (0, 1)], [(0, 0), (.3, .22), (.55, 0)], [(0, 1), (.3, .78), (.55, 1)]],
    'z': [[(.3, 0), (.3, 1)], [(.3, .4), (0, 0)], [(.3, .4), (.6, 0)]],
    's': [[(.55, 0), (.05, .42), (.55, .58), (.05, 1)]],
    't': [[(.3, 0), (.3, 1)], [(0, .3), (.3, 0), (.6, .3)]],
    'b': [[(0, 0), (0, 1)], [(0, 0), (.5, .25), (0, .5), (.5, .75), (0, 1)]],
    'e': [[(0, 0), (0, 1)], [(.6, 0), (.6, 1)], [(0, 0), (.3, .3), (.6, 0)]],
    'm': [[(0, 0), (0, 1)], [(.6, 0), (.6, 1)], [(0, 0), (.6, .45)], [(.6, 0), (0, .45)]],
    'l': [[(0, 0), (0, 1)], [(0, 0), (.5, .3)]],
    'ng': [[(.3, .2), (.6, .5), (.3, .8), (0, .5), (.3, .2)]],
    'd': [[(0, 0), (0, 1)], [(.6, 0), (.6, 1)], [(0, 0), (.6, 1)], [(.6, 0), (0, 1)]],
    'o': [[(.3, 0), (.6, .35), (.05, 1)], [(.3, 0), (0, .35), (.55, 1)]],
}
FUTHARK = ['f', 'u', 'th', 'a', 'r', 'k', 'g', 'w', 'h', 'n', 'i', 'j',
           'ei', 'p', 'z', 's', 't', 'b', 'e', 'm', 'l', 'ng', 'd', 'o']
THUNRAZ = ['th', 'u', 'n', 'r', 'a', 'z']        # *Thunraz: Thor, the thunder

IRON = ((8, 9, 10), (44, 45, 49), (98, 101, 108))    # albedo: shadow, mid, highlight (darkened after the first play test)
GLINT = (170, 205, 255)  # the runes' specular: they flare blue-white as the view moves across them
SILVER = (118, 122, 130)    # dull, worn: reads as engraving more than bright inlay
GROOVE = 9.0         # Sobel scale of the grooves in the normal map
RUST = 0.7            # how much of the old rust and blood shows through the iron


def _box(rect, size):
    w, h = size
    return rect[0] * w, rect[1] * h, rect[2] * w, rect[3] * h


def _rune(draw, name, x, y, height, width):
    for stroke in RUNES[name]:
        draw.line([(x + px * height, y + py * height) for px, py in stroke], fill=255, width=width, joint='curve')


def _braid(draw, x0, y0, x1, y1, width, vertical=True):
    """Two strands crossing over and under along a band, between two border lines."""
    if vertical:
        cx, half, length = (x0 + x1) / 2, (x1 - x0) / 2, y1 - y0
    else:
        cx, half, length = (y0 + y1) / 2, (y1 - y0) / 2, x1 - x0
    period = half * 2.6
    turns = max(1, round(length / period))
    period = length / turns
    steps = turns * 24
    amp = half * 0.62
    for phase in (0, math.pi):
        pts = []
        for i in range(steps + 1):
            t = i / steps * length
            off = amp * math.sin(2 * math.pi * t / period + phase)
            pts.append((cx + off, y0 + t) if vertical else (x0 + t, cx + off))
        draw.line(pts, fill=255, width=width, joint='curve')
    edge = [((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))] if vertical else [((x0, y0), (x1, y0)), ((x0, y1), (x1, y1))]
    for a, b in edge:
        draw.line([a, b], fill=255, width=max(1, width // 2))


def design():
    """(inlay, faces): the inlaid lines and the broad faces whose old inscription is smoothed away,
    as L masks at DESIGN size."""
    inlay = Image.new('L', DESIGN)
    faces = Image.new('L', DESIGN)
    d, f = ImageDraw.Draw(inlay), ImageDraw.Draw(faces)
    for rect in FACES:
        x0, y0, x1, y1 = _box(rect, DESIGN)
        f.rounded_rectangle((x0 + 14, y0 + 22, x1 - 14, y1 - 22), radius=40, fill=255)
        # The braid frame, inset from the face's rounded edge.
        m, band = 34, 26
        fx0, fy0, fx1, fy1 = x0 + m, y0 + m + 12, x1 - m, y1 - m - 12
        _braid(d, fx0, fy0 + band, fx0 + band, fy1 - band, 5)
        _braid(d, fx1 - band, fy0 + band, fx1, fy1 - band, 5)
        _braid(d, fx0 + band, fy0, fx1 - band, fy0 + band, 5, vertical=False)
        _braid(d, fx0 + band, fy1 - band, fx1 - band, fy1, 5, vertical=False)
        for cx, cy in ((fx0, fy0), (fx1 - band, fy0), (fx0, fy1 - band), (fx1 - band, fy1 - band)):
            d.rectangle((cx, cy, cx + band, cy + band), outline=255, width=4)
            d.line([(cx, cy), (cx + band, cy + band)], fill=255, width=3)
            d.line([(cx + band, cy), (cx, cy + band)], fill=255, width=3)
        # Inside: THUNRAZ large down the middle, the whole futhark small either side (12 a column).
        ix0, iy0, ix1, iy1 = fx0 + band + 18, fy0 + band + 20, fx1 - band - 18, fy1 - band - 20
        cx = (ix0 + ix1) / 2
        big = (iy1 - iy0) / (len(THUNRAZ) * 1.25)
        for i, name in enumerate(THUNRAZ):
            _rune(d, name, cx - big * 0.3, iy0 + i * big * 1.25 + big * 0.12, big, 9)
        small = (iy1 - iy0) / (12 * 1.3)
        for col, x in ((FUTHARK[:12], ix0 + 4), (FUTHARK[12:], ix1 - small * 0.6 - 4)):
            for i, name in enumerate(col):
                _rune(d, name, x, iy0 + i * small * 1.3 + small * 0.15, small, 4)
        d.line([(cx - big * 0.75, iy0), (cx - big * 0.75, iy1)], fill=255, width=3)
        d.line([(cx + big * 0.75, iy0), (cx + big * 0.75, iy1)], fill=255, width=3)
    x0, y0, x1, y1 = _box(SIDE, DESIGN)
    cx = (x0 + x1) / 2
    _braid(d, cx - 30, y0 + 40, cx + 30, y1 - 40, 6)
    return inlay, faces


def _fit(mask, size, blur=0.0):
    out = mask.resize(size, Image.LANCZOS if mask.size[0] > size[0] else Image.BICUBIC)
    return out.filter(ImageFilter.GaussianBlur(blur)) if blur else out


def _head(size):
    w, h = size
    m = Image.new('L', size)
    ImageDraw.Draw(m).rectangle((0, round(HEAD_TOP * h), w, h), fill=255)
    return m


def _smooth(im, faces, size):
    """`im` with the broad faces blurred: their carved inscription gone, their curve kept."""
    radius = max(2, size[0] / 2048 * 14)
    return Image.composite(im.filter(ImageFilter.GaussianBlur(radius)), im, _fit(faces, size, radius / 3))


def albedo(src, inlay, faces):
    size = src.size
    rgb, alpha = src.convert('RGB'), src.getchannel('A')
    lum = _smooth(ImageOps.grayscale(rgb), faces, size)
    lo, hi = 12, 150
    tone = lum.point(lambda v: max(0, min(255, round((v - lo) * 255 / (hi - lo)))))
    out = ImageOps.colorize(tone, IRON[0], IRON[2], IRON[1])
    # The silver, worn: darkened in patches and where the old block was grimy.
    lines = _fit(inlay, size, size[0] / 2048 * 0.8)
    wear = Image.effect_noise(size, 90).filter(ImageFilter.GaussianBlur(size[0] / 1024 * 3))
    wear = ImageChops.multiply(ImageOps.autocontrast(wear), ImageOps.autocontrast(ImageOps.grayscale(rgb), cutoff=1))
    silver = ImageChops.multiply(Image.new('RGB', size, SILVER), ImageOps.colorize(wear, (120, 120, 120), (255, 255, 255)))
    out = Image.composite(silver, out, lines)
    # Rust and old blood (the saturated texels) stay, over iron and silver alike.
    stain = rgb.convert('HSV').getchannel('S').point(lambda v: round(max(0, min(1, (v - 60) / 90)) * 255 * RUST))
    out = Image.composite(rgb, out, stain)
    out = Image.composite(out, rgb, _head(size))
    out.putalpha(alpha)
    return out


def normal(src, inlay, faces):
    size = src.size
    rgb = src.convert('RGB')
    flat = _smooth(rgb, faces, size)
    # Grooves: the inlay lines lie lower than the iron around them. This map's red grows as the
    # surface tilts toward the texture's left and its green as it tilts up (read off the block's
    # convex faces), so both rise with the height's slope along x and down y.
    height = ImageOps.invert(_fit(inlay, size, size[0] / 2048 * 1.6))
    # Sobel gradients, a full-height step giving about +-80. Pillow's kernel takes its rows bottom
    # up, so the y kernel is written upside down to give the slope down the image.
    dx = height.filter(ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1], scale=GROOVE, offset=128))
    dy = height.filter(ImageFilter.Kernel((3, 3), [1, 2, 1, 0, 0, 0, -1, -2, -1], scale=GROOVE, offset=128))
    r, g, b = flat.split()
    r = ImageChops.add(r, dx, 1.0, -128)
    g = ImageChops.add(g, dy, 1.0, -128)
    out = Image.merge('RGB', (r, g, b))
    out = Image.composite(out, rgb, _head(size))
    out.putalpha(src.getchannel('A') if src.mode == 'RGBA' else Image.new('L', size, 255))
    return out


def specular(src, inlay, faces):
    """Iron's specular: the old texture's grime pattern kept, pulled into a metal's range."""
    size = src.size
    rgb = src.convert('RGB')
    lum = _smooth(ImageOps.grayscale(rgb), faces, size)
    metal = lum.point(lambda v: round(40 + v * 45 / 255))
    iron = Image.merge('RGB', (metal, metal, metal))
    # The runes: a strong blue-white specular, so they flare as the camera or the light moves
    # across them (with the high gloss below), over their steady glow.
    iron = Image.composite(Image.new('RGB', size, GLINT), iron, _fit(inlay, size, size[0] / 2048 * 0.8))
    out = Image.composite(iron, rgb, _head(size))
    out.putalpha(src.getchannel('A') if src.mode == 'RGBA' else Image.new('L', size, 255))
    return out


def gloss(src, inlay, faces):
    size = src.size
    lum = _smooth(src.convert('L'), faces, size)
    metal = lum.point(lambda v: round(70 + v * 60 / 255))
    metal = Image.composite(Image.new('L', size, 235), metal, _fit(inlay, size, size[0] / 2048 * 0.8))   # a tight highlight
    return Image.composite(metal, src.convert('L'), _head(size))


ROLES = {'_a': albedo, '_n': normal, '_r': specular, '_s': gloss}
GLOW = (66, 96, 140)     # the runes' steady light: a soft blue (too bright at (120, 175, 255) in play)


def emissive(size, inlay):
    """The glow: black but for the runes and the braid, lit blue-white (BC1 sRGB, as the game's
    own emissive textures). The glow material's bloom does the rest."""
    lines = _fit(inlay, size, size[0] / 2048 * 0.6)
    out = Image.composite(Image.new('RGB', size, GLOW), Image.new('RGB', size), lines)
    out.putalpha(255)
    return Image.composite(out, Image.new('RGBA', size, (0, 0, 0, 255)), _head(size))


def role(name):
    """'_a', '_n', '_r' or '_s' of a texture name (WP_A_1031_a, WP_A_1031_n_l, ...)."""
    stem = name[:-2] if name.lower().endswith('_l') else name
    return stem[-2:].lower()


def retexture(tpf, glow=True):
    """Every texture of a ps4_texture.Ps4Tpf of the Kirkhammer's parts made rune-iron, in place,
    and (glow) an emissive texture added beside the albedo: <albedo name with _a as _e>, for the
    glow material the meshes are moved onto (weapon.py, flver.glow_material)."""
    inlay, faces = design()
    for t in tpf.textures:
        make = ROLES.get(role(t.name))
        if make is None:
            raise ValueError(f'{t.name}: not a texture this knows')
        t.set_image(make(t.image(), inlay, faces))
    if glow:
        albedo_tex = next(t for t in tpf.textures if role(t.name) == '_a')
        tpf.add_texture(emissive_name(albedo_tex.name), albedo_tex, emissive((albedo_tex.width, albedo_tex.height), inlay),
                        format_byte=0)


def emissive_name(albedo_name):
    """WP_A_1032_a -> WP_A_1032_e, WP_A_1032_a_l -> WP_A_1032_e_l."""
    low = albedo_name.endswith(('_l', '_L'))
    stem = albedo_name[:-2] if low else albedo_name
    return stem[:-2] + '_e' + albedo_name[len(stem):]


# --- previews ---------------------------------------------------------------------------------------
def lit(tpf, prefix, light=(-0.45, -0.55, 0.70)):
    """A rough render of a texture set: albedo lit through its normal map, with specular, for
    judging the look without the game."""
    a = tpf[prefix + '_a' + tpf.suffix].image().convert('RGB')
    n = tpf[prefix + '_n' + tpf.suffix].image().convert('RGB').resize(a.size, Image.BOX)
    r = tpf[prefix + '_r' + tpf.suffix].image().convert('L').resize(a.size, Image.BOX)
    ap, np_, rp = a.load(), n.load(), r.load()
    out = Image.new('RGB', a.size)
    op = out.load()
    ln = math.sqrt(sum(c * c for c in light))
    lx, ly, lz = (c / ln for c in light)
    hn = math.sqrt(lx * lx + ly * ly + (lz + 1) ** 2)
    hx, hy, hz = lx / hn, ly / hn, (lz + 1) / hn
    for y in range(a.size[1]):
        for x in range(a.size[0]):
            red, green, _ = np_[x, y]
            nx, ny = -(red - 128) / 127, -(green - 128) / 127    # the map's convention (normal())
            nz = math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
            d = max(0.0, nx * lx + ny * ly + nz * lz)
            s = max(0.0, nx * hx + ny * hy + nz * hz) ** 40 * rp[x, y] / 255 * 1.6
            op[x, y] = tuple(min(255, int(c * (0.25 + 1.6 * d) + 255 * s)) for c in a[x, y]) if False else \
                tuple(min(255, int(c * (0.25 + 1.6 * d) + 255 * s)) for c in ap[x, y])
    return out


def previews(dvdroot, out):
    """Before/after renders of the Kirkhammer's textures and the made textures themselves, into `out`."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fromsoft import Bnd4, dcx_decompress
    from ps4_texture import Ps4Tpf
    os.makedirs(out, exist_ok=True)
    for suffix in ('', '_l'):
        with open(os.path.join(dvdroot, 'parts', f'wp_a_1031{suffix}.partsbnd.dcx'), 'rb') as f:
            raw = Bnd4(dcx_decompress(f.read())).files[0]
        before, after = Ps4Tpf(raw), Ps4Tpf(raw)
        retexture(after)
        after = Ps4Tpf(after.to_bytes())    # as the game will read it, after BC encoding
        sheet = []
        for name, tpf in (('before', before), ('after', after)):
            tpf.suffix = suffix
            render = lit(tpf, 'WP_A_1031')
            render.save(os.path.join(out, f'{name}{suffix}_lit.png'))
            sheet.append(render)
            for t in tpf.textures:
                t.image().save(os.path.join(out, f'{name}_{t.name}.png'))
        w, h = sheet[0].size
        both = Image.new('RGB', (w, h * 2 + 8), (40, 40, 40))
        both.paste(sheet[0], (0, 0))
        both.paste(sheet[1], (0, h + 8))
        both.save(os.path.join(out, f'compare{suffix}.png'))
        top = round(HEAD_TOP * h)
        sheet[1].crop((0, top, w, h)).resize((w * 2, (h - top) * 2), Image.LANCZOS).save(
            os.path.join(out, f'head{suffix}_closeup.png'))


if __name__ == '__main__':
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Preview Thunderwright's rune-iron textures.")
    parser.add_argument('game', help='the game folder (with dvdroot_ps4)')
    parser.add_argument('out', help='folder for the preview PNGs')
    args = parser.parse_args()
    previews(os.path.join(args.game, 'dvdroot_ps4'), args.out)
