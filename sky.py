import csv
import gzip
import math
import random
import time
import pygame
import panel
import journal
import shooting
from pomodoro import Pomodoro

pygame.init()
WIDTH, HEIGHT = pygame.display.get_desktop_sizes()[0]
CX, CY = WIDTH // 2, HEIGHT // 2
RADIUS = int(HEIGHT * 0.55)
MIN_ALT = -70

# your location comes from config.py (kept private, not uploaded)
try:
    from config import LAT, LON
except ImportError:
    LAT, LON = 0.0, 0.0  # no config.py found, so set your own in config.py

MAX_MAG = 5.8

# Milky Way settings (change these to tune the look)
MW_POINTS = 3500
DUST_POINTS = 18000
CLOUD_RADIUS = int(HEIGHT * 0.04)
CLOUD_STRENGTH = 0.035
DUST_STRENGTH = 0.12
MW_REFRESH = 1800                # redraw the band every 1800 frames (60 sec)
MW_FULL_AT = 1500                # stars needed for the Milky Way at full strength

# Constellation line settings
LINE_GAP = 9                     # empty space near each star, in pixels
LINE_CORE = (125, 165, 140)      # thin bright line (soft sage)
LINE_MID = (30, 44, 36)          # soft glow around the line
LINE_WIDE = (14, 20, 17)         # very soft outer glow

# muted pink used for a newly unlocked constellation
LINE_CORE_PINK = (225, 170, 190)
LINE_MID_PINK = (52, 36, 42)
LINE_WIDE_PINK = (24, 17, 20)

FADE_TIME = 3.0                  # seconds to fade in
PINK_TIME = 8.0                  # seconds until pink turns back to sage
NEW_TIME = 4.0                   # seconds a new star pulses before it settles

# stars needed to unlock each constellation
COSTS = {
    "Crux": 150,
    "Cygnus": 300,
    "Orion": 450,
    "Big Dipper": 600,
    "Cassiopeia": 800,
    "Lyra": 900,
    "Leo": 1100,
    "Scorpius": 1400,
}

WHITE = (238, 243, 255)

COLORS = [
    (170, 195, 255),
    (228, 237, 255),
    (255, 248, 240),
    (255, 225, 185),
    (255, 190, 155),
]

# (brightness limit, glow radius). Smaller mag = brighter star
SIZES = [(0.0, 16), (1.0, 13), (2.0, 10), (3.0, 7), (4.0, 6), (4.8, 4), (99, 3)]

# twinkle levels: dim, normal, bright
LEVELS = [0.7, 1.0, 1.3]

# cloud colors: soft blue-grey, soft lilac, warm (used near the galaxy center)
CLOUD_COLORS = [(120, 135, 190), (150, 130, 185), (205, 170, 150)]

# Constellations: pairs of star IDs (Hipparcos numbers) that get a line
CONSTELLATIONS = {
    "Orion": [
        (26207, 27989), (26207, 25336), (27989, 26727), (25336, 25930),
        (26727, 26311), (26311, 25930), (26727, 27366), (25930, 24436),
    ],
    "Cassiopeia": [
        (746, 3179), (3179, 4427), (4427, 6686), (6686, 8886),
    ],
    "Big Dipper": [
        (54061, 53910), (53910, 58001), (58001, 59774), (59774, 54061),
        (59774, 62956), (62956, 65378), (65378, 67301),
    ],
    "Cygnus": [
        (95947, 100453), (100453, 102098), (97165, 100453), (100453, 102488),
    ],
    "Crux": [
        (60718, 61084), (62434, 59747),
    ],
    "Lyra": [
        (91262, 91971), (91971, 92791), (92791, 93194),
        (93194, 92420), (92420, 91971),
    ],
    "Leo": [
        (47908, 48455), (48455, 50335), (50335, 50583), (50583, 49583),
        (49583, 49669), (50583, 54872), (54872, 57632), (57632, 54879),
        (54879, 54872), (54879, 49669),
    ],
    "Scorpius": [
        (78820, 78401), (78401, 78265), (78401, 80112), (80112, 80763),
        (80763, 81266), (81266, 82396), (82396, 82514), (82514, 82729),
        (82729, 84143), (84143, 86228), (86228, 87073), (87073, 86670),
        (86670, 85927), (85927, 85696),
    ],
}


def color_index(ci):
    if ci < 0.0:
        return 0
    if ci < 0.4:
        return 1
    if ci < 0.9:
        return 2
    if ci < 1.3:
        return 3
    return 4


def size_index(mag):
    for i, (limit, _) in enumerate(SIZES):
        if mag < limit:
            return i
    return len(SIZES) - 1


def make_glow(radius, color, boost):
    size = radius * 2 + 1
    surf = pygame.Surface((size, size))
    for px in range(size):
        for py in range(size):
            d = math.hypot(px - radius, py - radius) / radius
            if d >= 1:
                continue
            glow = (1 - d) ** 3 * 0.55
            core = max(0.0, 1 - d * 4)
            v = min(1.0, (glow + core) * boost)
            surf.set_at((px, py), (int(color[0] * v), int(color[1] * v), int(color[2] * v)))
    return surf


def make_cloud(radius, color, strength):
    # very soft round light that fades out smoothly (no hard edge)
    size = radius * 2 + 1
    surf = pygame.Surface((size, size))
    for px in range(size):
        for py in range(size):
            d = math.hypot(px - radius, py - radius) / radius
            if d >= 1:
                continue
            v = math.exp(-3.5 * d * d) * strength
            surf.set_at((px, py), (int(color[0] * v), int(color[1] * v), int(color[2] * v)))
    return surf


# ---------- load stars ----------
stars = []
hip_index = {}  # star ID -> (ra, sin_dec, cos_dec), used for constellation lines
with gzip.open("hygdata_v42.csv.gz", "rt", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["mag"] == "" or row["ra"] == "" or row["dec"] == "":
            continue
        if row["proper"] == "Sol":
            continue
        mag = float(row["mag"])
        if mag >= MAX_MAG:
            continue
        ci = float(row["ci"]) if row["ci"] != "" else 0.6
        ra_deg = float(row["ra"]) * 15
        dec = math.radians(float(row["dec"]))
        if row["hip"] != "":
            hip_index[int(row["hip"])] = (ra_deg, math.sin(dec), math.cos(dec))
        stars.append((
            ra_deg,
            math.sin(dec),
            math.cos(dec),
            size_index(mag),
            color_index(ci),
            random.uniform(0, 6.28),
            mag,
        ))

stars.sort(key=lambda s: s[6])  # brightest stars first

# ---------- make the Milky Way ----------
# The Milky Way is a band around the sky. We make random points along it
# in galactic coordinates (l, b), then turn them into RA/Dec.
NGP_RA = math.radians(192.85948)
NGP_DEC = math.radians(27.12825)
L_NCP = math.radians(122.93192)


def galactic_to_equatorial(l_deg, b_deg):
    l = math.radians(l_deg)
    b = math.radians(b_deg)
    sin_dec = (math.sin(b) * math.sin(NGP_DEC)
               + math.cos(b) * math.cos(NGP_DEC) * math.cos(L_NCP - l))
    dec = math.asin(sin_dec)
    y = math.cos(b) * math.sin(L_NCP - l)
    x = (math.sin(b) * math.cos(NGP_DEC)
         - math.cos(b) * math.sin(NGP_DEC) * math.cos(L_NCP - l))
    ra = (NGP_RA + math.atan2(y, x)) % (2 * math.pi)
    return math.degrees(ra), dec


def center_weight(l):
    # 1.0 at the galaxy center (l = 0), lower on the far side
    return 0.25 + 0.75 * (0.5 + 0.5 * math.cos(math.radians(l)))


milky = []  # kind 0, 1, 2 = clouds, kind 3 = dust
while len(milky) < MW_POINTS:
    l = random.uniform(0, 360)
    if random.random() > center_weight(l):
        continue
    spread = 6 if random.random() < 0.6 else 10
    b = random.gauss(0, spread)
    ra, dec = galactic_to_equatorial(l, b)
    if math.cos(math.radians(l)) > 0.6 and random.random() < 0.3:
        kind = 2
    else:
        kind = random.choice([0, 0, 1])
    milky.append((ra, math.sin(dec), math.cos(dec), kind))

dust_count = 0
while dust_count < DUST_POINTS:
    l = random.uniform(0, 360)
    if random.random() > center_weight(l):
        continue
    b = random.gauss(0, 7)
    ra, dec = galactic_to_equatorial(l, b)
    milky.append((ra, math.sin(dec), math.cos(dec), 3))
    dust_count += 1


# ---------- window and images ----------
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Jadebit Sky")
clock = pygame.time.Clock()
ui = panel.Panel()
journal_view = journal.Journal()
pomo = Pomodoro()  # pomodoro timer (no audio). Minimizes to a little clock, bottom right
shooters = shooting.ShootingStars(WIDTH, HEIGHT)

# background gradient (made once)
bg = pygame.Surface((WIDTH, HEIGHT))
for y in range(HEIGHT):
    t = y / HEIGHT
    pygame.draw.line(bg, (int(7 + 9 * t), int(9 + 9 * t), int(20 + 16 * t)), (0, y), (WIDTH, y))

# star glow images (made once, reused for every star)
glows = [
    [[make_glow(r, c if i < 4 else WHITE, b) for b in LEVELS] for c in COLORS]
    for i, (_, r) in enumerate(SIZES)
]

# Milky Way images (made once)
clouds = [make_cloud(CLOUD_RADIUS, c, CLOUD_STRENGTH) for c in CLOUD_COLORS]
dust_img = make_cloud(2, (205, 215, 245), DUST_STRENGTH)

sin_lat = math.sin(math.radians(LAT))
cos_lat = math.cos(math.radians(LAT))


def local_sidereal_deg():
    jd = time.time() / 86400 + 2440587.5
    gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0)
    return (gmst + LON) % 360


def project(ra, sin_dec, cos_dec, lst):
    ha = math.radians(lst - ra)
    sin_alt = sin_dec * sin_lat + cos_dec * cos_lat * math.cos(ha)
    alt = math.degrees(math.asin(sin_alt))
    if alt < MIN_ALT:
        return None
    x = cos_dec * math.sin(ha)
    y = cos_dec * math.cos(ha) * sin_lat - sin_dec * cos_lat
    az = math.atan2(x, y) + math.pi
    r = (90 - alt) / 90 * RADIUS
    return CX + r * math.sin(az), CY - r * math.cos(az)


def update_stars():
    lst = local_sidereal_deg()
    vis = []
    for i, (ra, sin_dec, cos_dec, si, ci, phase, mag) in enumerate(stars[:ui.data["total_stars"]]):
        pos = project(ra, sin_dec, cos_dec, lst)
        if pos:
            vis.append((pos[0], pos[1], si, ci, phase, i))
    return vis


def build_milky_way():
    # draw the whole band onto one picture, so we only do this once in a while
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    lst = local_sidereal_deg()
    for ra, sin_dec, cos_dec, kind in milky:
        pos = project(ra, sin_dec, cos_dec, lst)
        if not pos:
            continue
        if kind == 3:
            surf.blit(dust_img, (int(pos[0]) - 2, int(pos[1]) - 2),
                      special_flags=pygame.BLEND_RGB_ADD)
        else:
            surf.blit(clouds[kind], (int(pos[0]) - CLOUD_RADIUS, int(pos[1]) - CLOUD_RADIUS),
                      special_flags=pygame.BLEND_RGB_ADD)
    return surf


# ---------- constellation unlocking ----------
def mix(a, b, t):
    # blend color a toward color b (t = 0 gives a, t = 1 gives b)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(c, k):
    return tuple(int(v * k) for v in c)


unlocked_at = {}  # name -> time it unlocked (0 = was already unlocked at start)


def check_unlocks(first_run=False):
    total = ui.data["total_stars"]
    for name, cost in COSTS.items():
        if total >= cost and name not in unlocked_at:
            unlocked_at[name] = 0 if first_run else time.time()
        elif total < cost and name in unlocked_at:
            del unlocked_at[name]  # locks again if you lose stars


def build_lines():
    # draw all unlocked constellation lines on one picture
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    lst = local_sidereal_deg()
    now = time.time()
    for name, pairs in CONSTELLATIONS.items():
        if name not in unlocked_at:
            continue
        age = now - unlocked_at[name]
        fade = min(1.0, age / FADE_TIME)
        warm = max(0.0, 1 - age / PINK_TIME)
        core = scale(mix(LINE_CORE, LINE_CORE_PINK, warm), fade)
        mid = scale(mix(LINE_MID, LINE_MID_PINK, warm), fade)
        wide = scale(mix(LINE_WIDE, LINE_WIDE_PINK, warm), fade)
        for a, b in pairs:
            if a not in hip_index or b not in hip_index:
                continue
            pa = project(*hip_index[a], lst)
            pb = project(*hip_index[b], lst)
            if not pa or not pb:
                continue
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            length = math.hypot(dx, dy)
            if length < 2 * LINE_GAP + 2:
                continue
            ux, uy = dx / length, dy / length
            p1 = (pa[0] + ux * LINE_GAP, pa[1] + uy * LINE_GAP)
            p2 = (pb[0] - ux * LINE_GAP, pb[1] - uy * LINE_GAP)
            pygame.draw.line(surf, wide, p1, p2, 7)
            pygame.draw.line(surf, mid, p1, p2, 3)
            pygame.draw.line(surf, core, p1, p2, 1)
    return surf


def fade_mw(base):
    # makes the Milky Way dimmer when you have fewer stars
    level = min(1.0, ui.data["total_stars"] / MW_FULL_AT)
    v = int(255 * level)
    s = base.copy()
    s.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
    return s


prev_total = ui.data["total_stars"]
born = {}  # star number -> time it was added (for the new-star effect)
visible = update_stars()
mw_base = build_milky_way()
mw_surface = mw_base
last_total = -1
check_unlocks(True)
lines_surface = build_lines()
show_lines = True
frame = 0
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN and not ui.typing:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_f:
                pygame.display.toggle_fullscreen()
            if event.key == pygame.K_c:
                show_lines = not show_lines
            if event.key == pygame.K_j:
                journal_view.toggle()
            if event.key == pygame.K_t:
                pomo.toggle_minimized()  # T = minimize / open the pomodoro
        ui.handle_event(event)
        journal_view.handle_event(event)
        pomo.handle_event(event)

    frame += 1
    check_unlocks()

    # when the star count changes, mark new stars and refresh right away
    total = ui.data["total_stars"]
    if total != prev_total:
        if total > prev_total:
            for n in range(prev_total, total):
                born[n] = time.time()
            if total >= shooting.SHOOT_AT:
                shooters.spawn()
        else:
            for n in [k for k in born if k >= total]:
                del born[n]
        prev_total = total
        visible = update_stars()

    now = time.time()
    animating = any(now - t < PINK_TIME for t in unlocked_at.values())
    if frame % 30 == 0:
        visible = update_stars()
        born = {k: v for k, v in born.items() if now - v < NEW_TIME}
    if frame % 30 == 0 or (animating and frame % 2 == 0):
        lines_surface = build_lines()
    if frame % MW_REFRESH == 0:
        mw_base = build_milky_way()
        last_total = -1
    if ui.data["total_stars"] != last_total:
        last_total = ui.data["total_stars"]
        mw_surface = fade_mw(mw_base)

    screen.blit(bg, (0, 0))
    screen.blit(mw_surface, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    if show_lines:
        screen.blit(lines_surface, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    shooters.update(ui.data["total_stars"])
    shooters.draw(screen)

    t = time.time()
    rings = []
    for x, y, si, ci, phase, n in visible:
        if n in born:
            age = t - born[n]
            if age < NEW_TIME:
                si = int(si * age / NEW_TIME)  # starts big, settles to normal size
                rings.append((x, y, age))
        level = int(1 + round(math.sin(t * 0.8 + phase)))
        g = glows[si][ci][level]
        screen.blit(g, (int(x) - g.get_width() // 2, int(y) - g.get_height() // 2),
                    special_flags=pygame.BLEND_RGB_ADD)

    # pink rings around new stars
    for x, y, age in rings:
        for delay in (0.0, 0.6):
            a = age - delay
            if 0 < a < 2.0:
                p = a / 2.0
                color = scale(LINE_CORE_PINK, (1 - p) * 0.9)
                pygame.draw.circle(screen, color, (int(x), int(y)), int(8 + 45 * p), 1)

    ui.draw(screen)
    journal_view.draw(screen)
    pomo.draw(screen)
    pygame.display.flip()
    clock.tick(30)

pygame.quit()