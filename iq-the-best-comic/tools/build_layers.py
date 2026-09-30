"""Cut the iQ The Best! cover into animation layers.

Usage:
  python3 build_layers.py COVER.png --lama big-lama.pt [--esrgan RealESRGAN_x4plus_anime_6B.pth]
                          [--upscaled COVER_x4.png] --export 2:assets --export 4:assets4

Produces, for each export: plate.jpg (the shop with everyone painted out and the room rebuilt),
title.webp, <name>.webp (one complete RGBA figure per character) and layers.json.

Needs: rembg (isnet-anime and sam models), torch, opencv-python-headless, numpy, pillow,
the LaMa inpainting model (big-lama.pt, TorchScript) and optionally the Real-ESRGAN anime 6B weights.
All coordinates below are in the original 1024 x 1536 cover's pixel space.
"""
import argparse, json, os
import numpy as np, cv2, torch
from PIL import Image

W0, H0 = 1024, 1536
NAMES = ['marcin', 'freddie', 'fin', 'jess', 'elena']
# Who is in front where silhouettes overlap (higher wins).
DEPTH = {'marcin': 1, 'elena': 2, 'freddie': 3, 'jess': 4, 'fin': 5}
# Click prompts for Segment Anything: points on each character (pos) and on neighbours or furniture (neg).
PROMPTS = {
    'marcin': {'box': (0, 520, 340, 1420), 'pos': [(185, 620), (180, 760), (100, 850), (250, 835), (80, 1100), (140, 1230), (60, 1340), (150, 570), (75, 650)], 'neg': [(370, 790), (330, 950), (15, 900), (300, 1100)]},
    'freddie': {'box': (170, 690, 480, 1420), 'pos': [(370, 790), (340, 930), (300, 950), (320, 1150), (260, 1250), (240, 1360), (390, 1340), (425, 1050), (360, 730)], 'neg': [(190, 780), (250, 800), (470, 830), (520, 1000), (200, 1320)]},
    'fin': {'box': (390, 540, 640, 1420), 'pos': [(505, 630), (520, 760), (460, 820), (580, 860), (510, 950), (490, 1150), (560, 1200), (460, 1360), (560, 1320), (490, 580)], 'neg': [(370, 790), (660, 740), (440, 960), (620, 1000)]},
    'jess': {'box': (570, 620, 900, 1420), 'pos': [(690, 745), (680, 870), (760, 850), (830, 835), (650, 700), (660, 1040), (650, 1200), (760, 1200), (650, 1340), (790, 1340), (735, 1070)], 'neg': [(560, 760), (900, 875), (930, 960), (800, 1150), (560, 1100)]},
    'elena': {'box': (740, 720, 1024, 1480), 'pos': [(900, 875), (920, 990), (850, 930), (980, 900), (900, 1060), (870, 1200), (950, 1200), (830, 1400), (960, 1390), (790, 1000), (940, 1100)], 'neg': [(795, 1100), (985, 1100), (975, 1230), (805, 1240), (720, 1000), (840, 845), (760, 1150)]},
}
TITLE = {'box': (0, 0, 1024, 330), 'pos': [(70, 120), (175, 110), (430, 150), (700, 120), (560, 120), (300, 40), (900, 60), (600, 230), (960, 130), (40, 60), (250, 200), (958, 200), (950, 165)],
         'neg': [(200, 300), (800, 300), (105, 310), (480, 290), (20, 300), (1000, 300)]}
# Hidden parts of each figure (behind whoever stands in front), completed by inpainting from their surroundings.
HIDDEN = {
    'freddie': [[(395, 1295), (452, 1300), (456, 1378), (395, 1378)]],
    'elena': [[(776, 790), (892, 818), (894, 878), (840, 888), (788, 888)]],
}
# Which filled pixels actually belong to the figure (the rest was background behind them).
HIDDEN_KEEP = {'freddie': 'dark', 'elena': 'red'}
# Marcin's right side, hidden behind Freddie, is rebuilt by mirroring his left side about this axis,
# only inside these bands (shoulder to belt, and the boot).
MIRROR = {'marcin': {'axis': 172, 'min_x': 186, 'bands': [(830, 1362)]}}
# Back counters: the white drawer unit on the far left of the cover (half hidden behind Marcin, so taken
# once the room is rebuilt) is repeated along the back of the room, in the cover's own style.
CABINET = {'src': (18, 815, 172, 1010), 'x0': 172, 'x1': 1008, 'floor': (1008, 1115)}
# Bits of figures the matte misses (Marcin's far boot between Freddie's feet): always painted out of the room.
CLEAN = [[(165, 1280), (345, 1280), (345, 1365), (165, 1365)]]
# Split lines between neighbours: pixels on the wrong side of these are stray bits of someone else.
B1 = [(320, 0), (320, 500), (310, 720), (302, 760), (300, 850), (235, 868), (222, 960), (210, 1060), (188, 1120), (178, 1300), (172, 1536)]
B4 = [(735, 0), (735, 500), (737, 770), (785, 795), (878, 826), (884, 860), (842, 876), (800, 882), (796, 960), (772, 1000), (766, 1100), (792, 1200), (790, 1290), (842, 1300), (846, 1420), (760, 1536)]
# Background showing through gaps the matte closed over (between Fin's legs): bright pixels here are not the figure.
GAPS = {'fin': [(498, 995), (530, 995), (532, 1302), (496, 1302)], 'jess': [(720, 1150), (756, 1150), (756, 1260), (720, 1260)]}
# Places where the usual front-to-back order flips: Elena's platform boot stands in front of Jess's trainer.
IN_FRONT = [('elena', [(760, 1290), (905, 1290), (905, 1475), (760, 1475)])]
ZONES = {'freddie': B1 + [(W0, H0), (W0, 0)], 'jess': [(0, 0)] + B4 + [(0, H0)]}


def poly_mask(polys):
    im = Image.new('L', (W0, H0), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    for p in polys: d.polygon(p, fill=255)
    return np.array(im) > 127


def fill_holes(m, max_area, allow=None):
    inv = (~m).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(inv, 4)
    H, W = m.shape
    for k in range(1, n):
        x, y, w, h, area = st[k]
        if x > 0 and y > 0 and x + w < W and y + h < H and area < max_area:
            m |= (cc == k) if allow is None else ((cc == k) & allow)
    return m


def drop_shards(m, k=13, grow=9):
    """Remove bits hanging on by thin necks (usually a neighbour's pixels)."""
    core = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(bool)
    core = keep_main(core, 3, 400)
    return m & (cv2.dilate(core.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow))) > 0)


def keep_main(m, near=31, min_area=150):
    cnt, cc, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if cnt <= 1: return m
    main_k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    near_main = cv2.dilate((cc == main_k).astype(np.uint8), np.ones((near, near), np.uint8)).astype(bool)
    keep = [k for k in range(1, cnt) if k == main_k or (stats[k, cv2.CC_STAT_AREA] > min_area and (near_main & (cc == k)).any())]
    return np.isin(cc, keep)


def push_pull(img, known):
    """Smooth fill of unknown pixels from their surroundings."""
    levels = []
    c, w = img.astype(np.float32) * known[..., None], known.astype(np.float32)
    while min(c.shape[:2]) > 4:
        levels.append((c, w))
        c = cv2.resize(c, (c.shape[1] // 2, c.shape[0] // 2), interpolation=cv2.INTER_AREA) * 4
        w = cv2.resize(w, (w.shape[1] // 2, w.shape[0] // 2), interpolation=cv2.INTER_AREA) * 4
    est = c / np.maximum(w, 1e-4)[..., None]
    for c, w in reversed(levels):
        up = cv2.resize(est, (c.shape[1], c.shape[0]), interpolation=cv2.INTER_LINEAR)
        a = np.clip(w, 0, 1)[..., None]
        est = (c / np.maximum(w, 1e-4)[..., None]) * a + up * (1 - a)
    return est


class Lama:
    def __init__(self, path):
        self.m = torch.jit.load(path, map_location='cpu').eval()

    def __call__(self, img, hole):
        H, W = img.shape[:2]; ph, pw = (8 - H % 8) % 8, (8 - W % 8) % 8
        i = np.pad(img, ((0, ph), (0, pw), (0, 0)), mode='reflect'); h = np.pad(hole, ((0, ph), (0, pw)))
        it = torch.from_numpy(np.ascontiguousarray(i)).permute(2, 0, 1)[None].float() / 255
        mt = torch.from_numpy(h)[None, None].float()
        with torch.no_grad():
            o = self.m(it, mt)[0].permute(1, 2, 0).clamp(0, 1).numpy() * 255
        out = img.copy(); o = o[:H, :W].astype(np.uint8); out[hole] = o[hole]
        return out


class Esrgan:
    """Real-ESRGAN x4plus anime 6B, run on tiles."""
    def __init__(self, path):
        import torch.nn as nn, torch.nn.functional as F
        class RDB(nn.Module):
            def __init__(s, nf=64, gc=32):
                super().__init__()
                s.conv1 = nn.Conv2d(nf, gc, 3, 1, 1); s.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1); s.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
                s.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1); s.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1); s.l = nn.LeakyReLU(0.2, True)
            def forward(s, x):
                x1 = s.l(s.conv1(x)); x2 = s.l(s.conv2(torch.cat((x, x1), 1))); x3 = s.l(s.conv3(torch.cat((x, x1, x2), 1)))
                x4 = s.l(s.conv4(torch.cat((x, x1, x2, x3), 1))); return s.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x
        class RRDB(nn.Module):
            def __init__(s):
                super().__init__(); s.rdb1 = RDB(); s.rdb2 = RDB(); s.rdb3 = RDB()
            def forward(s, x): return s.rdb3(s.rdb2(s.rdb1(x))) * 0.2 + x
        class Net(nn.Module):
            def __init__(s, nb=6, nf=64):
                super().__init__(); s.conv_first = nn.Conv2d(3, nf, 3, 1, 1); s.body = nn.Sequential(*[RRDB() for _ in range(nb)]); s.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
                s.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1); s.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1); s.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1); s.conv_last = nn.Conv2d(nf, 3, 3, 1, 1); s.l = nn.LeakyReLU(0.2, True)
            def forward(s, x):
                f = s.conv_first(x); f = f + s.conv_body(s.body(f))
                f = s.l(s.conv_up1(F.interpolate(f, scale_factor=2, mode='nearest'))); f = s.l(s.conv_up2(F.interpolate(f, scale_factor=2, mode='nearest')))
                return s.conv_last(s.l(s.conv_hr(f)))
        self.net = Net(); sd = torch.load(path, map_location='cpu'); sd = sd.get('params_ema', sd.get('params', sd))
        self.net.load_state_dict(sd, strict=True); self.net.eval()

    def __call__(self, img, only=None, base=None, T=192, P=16):
        """Upscale img x4. With `only` (bool mask), tiles not touching it are copied from `base` (already x4)."""
        H, W, _ = img.shape
        out = base.copy() if base is not None else np.zeros((H * 4, W * 4, 3), np.uint8)
        f = img.astype(np.float32) / 255
        with torch.no_grad():
            for y in range(0, H, T):
                for x in range(0, W, T):
                    if only is not None and not only[y:y + T, x:x + T].any(): continue
                    y0, x0 = max(0, y - P), max(0, x - P); y1, x1 = min(H, y + T + P), min(W, x + T + P)
                    o = self.net(torch.from_numpy(np.ascontiguousarray(f[y0:y1, x0:x1].transpose(2, 0, 1)))[None])[0].clamp(0, 1).numpy().transpose(1, 2, 0)
                    oy, ox = (y - y0) * 4, (x - x0) * 4; h, w = min(T, H - y) * 4, min(T, W - x) * 4
                    out[y * 4:y * 4 + h, x * 4:x * 4 + w] = (o[oy:oy + h, ox:ox + w] * 255 + 0.5).astype(np.uint8)
        return out


def segment(cover):
    from rembg import remove, new_session
    soft = np.array(remove(cover, session=new_session('isnet-anime'), only_mask=True)).astype(np.float32) / 255
    sam = new_session('sam')
    def sam_mask(p):
        x0, y0, x1, y1 = p['box']
        prompt = [{'type': 'point', 'data': [x - x0, y - y0], 'label': 1} for x, y in p['pos']] + [{'type': 'point', 'data': [x - x0, y - y0], 'label': 0} for x, y in p['neg']]
        m = np.zeros((H0, W0), bool)
        m[y0:y1, x0:x1] = np.array(remove(cover.crop(p['box']), session=sam, sam_prompt=prompt, only_mask=True)) > 127
        return m
    lab = np.full((H0, W0), -1, np.int32)
    arr = np.array(cover).astype(np.int32)
    body = soft > 0.25
    redhair = (arr[..., 0] > 100) & (arr[..., 0] > arr[..., 1] * 1.8) & (arr[..., 0] > arr[..., 2] * 2.2)
    masks = {}
    for n in sorted(NAMES, key=lambda n: DEPTH[n]):
        sm = sam_mask(PROMPTS[n])
        sm = fill_holes(cv2.morphologyEx(sm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool), 6000, body)
        near = cv2.dilate(sm.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        m = (sm & (soft > 0.05)) | (near & (soft > 0.35)) | cv2.erode(sm.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        if n in ZONES: m &= poly_mask([ZONES[n]])
        if n == 'jess': m &= ~redhair
        if n in GAPS: m &= ~(poly_mask([GAPS[n]]) & (arr.sum(-1) > 480))
        m = drop_shards(keep_main(fill_holes(m, 3000, body)))
        lab[m] = NAMES.index(n)
        masks[n] = m
    for n, poly in IN_FRONT:
        lab[masks[n] & poly_mask([poly])] = NAMES.index(n)
    # title: SAM, minus the blue ceiling it bleeds into
    t = sam_mask(TITLE)
    blue = (arr[..., 2] > arr[..., 0] + 25) & (arr[..., 2] > 110)
    t &= ~blue; t[:14] = False
    t = cv2.morphologyEx(t.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    t = fill_holes(keep_main(t, 15, 60), 5000)
    return lab, t


def build_plate(a, img, x4, lab, title, lama, esr):
    anyfg = (lab >= 0).astype(np.uint8)
    hole = cv2.dilate(anyfg, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))) > 0
    hole |= cv2.dilate(title.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    for polys in HIDDEN.values(): hole |= cv2.dilate(poly_mask(polys).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    hole |= poly_mask(CLEAN)
    # Fill at half size: the gap is large, and the model keeps the room's structure better at this scale.
    print('rebuilding the room')
    half = cv2.resize(img, (W0 // 2, H0 // 2), interpolation=cv2.INTER_AREA)
    hh = cv2.resize(hole.astype(np.uint8), (W0 // 2, H0 // 2), interpolation=cv2.INTER_NEAREST) > 0
    up2 = cv2.resize(lama(half, hh), (W0, H0), interpolation=cv2.INTER_CUBIC)
    plate1 = img.copy(); plate1[hole] = up2[hole]
    # line the back of the room with the cover's own drawer units, then let the model blend the joins
    x0, y0, x1, y1 = CABINET['src']; unit = plate1[y0:y1, x0:x1].copy(); uw = x1 - x0
    band = np.zeros_like(hole); seams = np.zeros_like(hole)
    x = CABINET['x0']; flip = False
    while x < CABINET['x1']:
        w = min(uw, CABINET['x1'] - x); u = unit[:, ::-1] if flip else unit
        region = hole[y0:y1, x:x + w]
        plate1[y0:y1, x:x + w][region] = u[:, :w][region]
        band[y0:y1, x:x + w] |= region
        x += uw; flip = not flip
    seams[y1 - 3:y1 + 12, CABINET['x0']:CABINET['x1']] = True
    seams[y0 - 10:y0 + 3, CABINET['x0']:CABINET['x1']] = True
    for xe in (CABINET['x0'], CABINET['x1']): seams[y0 - 10:y1 + 12, xe - 8:xe + 8] = True
    fy0, fy1 = CABINET['floor']; seams[fy0:fy1, :] = True   # the strip of floor in front of the counters
    seams &= hole
    plate1 = lama(plate1, seams)
    Image.fromarray(plate1).save(f'{a.cache}/plate_1x.png')
    holeB = cv2.resize(hole.astype(np.uint8), (W0 * 4, H0 * 4), interpolation=cv2.INTER_NEAREST).astype(bool)
    if esr:
        print('sharpening the rebuilt room'); up = esr(plate1, only=hole, base=x4)
    else:
        up = cv2.resize(plate1, (W0 * 4, H0 * 4), interpolation=cv2.INTER_CUBIC)
    feather = cv2.GaussianBlur(holeB.astype(np.float32), (0, 0), 6)[..., None]
    return (x4 * (1 - feather) + up * feather).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cover')
    ap.add_argument('--lama', required=True)
    ap.add_argument('--esrgan', default=None)
    ap.add_argument('--upscaled', default=None, help='cover already upscaled x4 (saves a long ESRGAN pass)')
    ap.add_argument('--export', action='append', required=True, help='SCALE:DIR, e.g. 2:assets')
    ap.add_argument('--cache', default='.layer-cache')
    ap.add_argument('--reuse-plate', action='store_true', help='reuse the rebuilt room from the cache')
    a = ap.parse_args()
    torch.set_num_threads(os.cpu_count() or 4)
    os.makedirs(a.cache, exist_ok=True)
    cover = Image.open(a.cover).convert('RGB').resize((W0, H0), Image.LANCZOS)
    img = np.array(cover)
    esr = Esrgan(a.esrgan) if a.esrgan else None
    if a.upscaled: x4 = np.array(Image.open(a.upscaled).convert('RGB').resize((W0 * 4, H0 * 4), Image.LANCZOS))
    elif esr: x4 = esr(img)
    else: x4 = np.array(cover.resize((W0 * 4, H0 * 4), Image.LANCZOS))

    print('segmenting'); lab, title = segment(cover)
    np.save(f'{a.cache}/lab.npy', lab); np.save(f'{a.cache}/title.npy', title)
    lama = Lama(a.lama)

    # --- the room, rebuilt behind everyone ---
    plate_cache = f'{a.cache}/plate_x4.png'
    if a.reuse_plate and os.path.exists(plate_cache):
        plate4 = np.array(Image.open(plate_cache))
    else:
        plate4 = build_plate(a, img, x4, lab, title, lama, esr)
        Image.fromarray(plate4).save(plate_cache)


    # --- complete figures ---
    figs = {}
    for i, n in enumerate(NAMES):
        own = lab == i
        hidden = poly_mask(HIDDEN[n]) & ~own if n in HIDDEN else np.zeros_like(own)
        rgb4 = x4.copy()
        if n in MIRROR:
            mi = MIRROR[n]; ax = mi['axis']
            xs = np.arange(W0); src = np.clip(2 * ax - xs, 0, W0 - 1)
            mm = own[:, src] & ~own
            band = np.zeros_like(own)
            for y0, y1 in mi['bands']: band[y0:y1] = True
            mm &= band & (xs[None, :] >= mi['min_x'])
            xs4 = np.arange(W0 * 4); src4 = np.clip(2 * ax * 4 - xs4, 0, W0 * 4 - 1)
            mm4 = cv2.resize(mm.astype(np.uint8), (W0 * 4, H0 * 4), interpolation=cv2.INTER_NEAREST).astype(bool)
            mirrored = x4[:, src4]
            rgb4[mm4] = mirrored[mm4]
            own = own | mm
        if hidden.any():
            # repaint whoever is in front out of the way, using the real surroundings as context
            done = lama(img, hidden)
            keep = HIDDEN_KEEP.get(n)
            if keep:
                d = done.astype(np.int32)
                ok = (d.sum(-1) < 240) if keep == 'dark' else ((d[..., 0] > d[..., 1] * 1.4) & (d[..., 0] > 70))
                ok = cv2.morphologyEx(ok.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
                hidden &= ok
                hidden &= cv2.dilate(own.astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool)
            hid4 = cv2.resize(hidden.astype(np.uint8), (W0 * 4, H0 * 4), interpolation=cv2.INTER_NEAREST).astype(bool)
            patch = esr(done, only=hidden, base=np.zeros_like(x4)) if esr else cv2.resize(done, (W0 * 4, H0 * 4), interpolation=cv2.INTER_CUBIC)
            rgb4[hid4] = patch[hid4]
        figs[n] = (own | hidden, rgb4)

    for spec in a.export:
        S, out = spec.split(':', 1); S = int(S)
        os.makedirs(out, exist_ok=True)
        W, H = W0 * S, H0 * S
        rs = lambda im: cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
        Image.fromarray(rs(plate4)).save(f'{out}/plate.jpg', quality=90)
        meta = {'scale': S, 'size': [W0, H0], 'layers': {}}
        def export(name, mask, rgb4):
            alpha = cv2.resize(mask.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
            alpha = cv2.GaussianBlur(alpha, (0, 0), 0.35 * S)
            ys, xs = np.nonzero(alpha > 0.01)
            x0, x1, y0, y1 = max(0, xs.min() - 4), min(W, xs.max() + 5), max(0, ys.min() - 4), min(H, ys.max() + 5)
            rgba = np.dstack([rs(rgb4), (np.clip(alpha, 0, 1) * 255).astype(np.uint8)])[y0:y1, x0:x1]
            Image.fromarray(rgba, 'RGBA').save(f'{out}/{name}.webp', quality=92, method=6)
            meta['layers'][name] = {'x': float(x0 / S), 'y': float(y0 / S), 'w': float((x1 - x0) / S), 'h': float((y1 - y0) / S)}
        for n, (mask, rgb4) in figs.items(): export(n, mask, rgb4)
        export('title', title, x4)
        json.dump(meta, open(f'{out}/layers.json', 'w'), indent=1)
        print('exported', out, meta['layers'])


if __name__ == '__main__':
    main()
