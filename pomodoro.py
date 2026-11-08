import json
import math
import os
import time
import pygame

CREAM = (255, 244, 225)
SAGE = (150, 185, 165)
PINK = (225, 170, 190)
DIM = (125, 135, 160)
FAINT = (60, 68, 100)
PANEL_BG = (14, 17, 32, 215)
PANEL_BORDER = (70, 80, 115, 160)
CLOCK_BODY = (18, 21, 40)        # the minimized clock is solid so its ears look clean
CLOCK_EAR = (26, 30, 54)
CLOCK_EDGE = (70, 80, 115)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "pomodoro_data.json")   # your settings and your log live here

CARD_POS = "top-right"     # where the full card sits: "top-right" or "bottom-right"
MARGIN = 30                # distance from the screen edges
CLOCK_R = 40               # size of the minimized clock

DEFAULTS = {"focus": 25, "short": 5, "long": 15, "every": 4}
LIMITS = {"focus": (1, 180), "short": (1, 60), "long": (1, 120), "every": (2, 10)}
LABELS = {"focus": "Focus", "short": "Short break", "long": "Long break",
          "every": "Long break every"}
STYLE = {"focus": ("FOCUS", SAGE), "short": ("SHORT BREAK", PINK), "long": ("LONG BREAK", PINK)}

LOG_ROWS = 6          # how many log lines fit on the card
MIN_LOGGED = 60       # a stopped session shorter than this many seconds is not logged
FLASH_TIME = 8        # seconds the "done" signal shows after a session ends


def load_data():
    settings = dict(DEFAULTS)
    log = []
    minimized = False
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        for k, v in data.get("settings", {}).items():
            if k in settings and isinstance(v, int):
                lo, hi = LIMITS[k]
                settings[k] = max(lo, min(hi, v))
        log = [e for e in data.get("log", []) if "t" in e and "done" in e]
        minimized = bool(data.get("minimized", False))
    except (OSError, ValueError):
        pass
    return settings, log, minimized


def fmt_minutes(seconds):
    m = int(round(seconds / 60))
    h, m = divmod(m, 60)
    return "%dh %02dm" % (h, m) if h else "%dm" % m


def midnight(ts):
    d = time.localtime(ts)
    return time.mktime((d.tm_year, d.tm_mon, d.tm_mday, 0, 0, 0, 0, 0, -1))


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy - r * math.sin(a))


class Pomodoro:
    W = 380

    def __init__(self):
        self.big = pygame.font.Font(None, 64)
        self.font = pygame.font.Font(None, 28)
        self.small = pygame.font.Font(None, 22)
        self.tiny = pygame.font.Font(None, 18)
        self.clock_font = pygame.font.Font(None, 30)
        self.settings, self.log, self.minimized = load_data()
        self.view = "timer"          # "timer", "settings" or "log"
        self.mode = "focus"
        self.remaining = self.length("focus")
        self.running = False
        self.end = 0.0               # clock time when the timer hits zero (while running)
        self.done = 0                # focus sessions finished since the game started
        self.flash_until = 0.0
        self.session_start = None    # when the current focus session began (for the log)
        self.session_total = 0.0
        self.log_scroll = 0
        self.rect = None
        self.buttons = {}

    # ---------- saving ----------
    def save(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({"settings": self.settings, "log": self.log,
                           "minimized": self.minimized}, f, indent=1)
        except OSError:
            pass

    def set_minimized(self, value):
        self.minimized = value
        self.view = "timer"
        self.save()

    def toggle_minimized(self):
        self.set_minimized(not self.minimized)

    # ---------- timer ----------
    def length(self, mode):
        return float(self.settings[mode] * 60)

    def time_left(self):
        if self.running:
            return max(0.0, self.end - time.time())
        return self.remaining

    def start(self):
        if self.remaining <= 0:
            self.remaining = self.length(self.mode)
        if self.mode == "focus" and self.session_start is None:
            self.session_start = time.time()
            self.session_total = self.remaining
        self.end = time.time() + self.remaining
        self.running = True

    def pause(self):
        self.remaining = self.time_left()
        self.running = False

    def toggle_run(self):
        if self.running:
            self.pause()
        else:
            self.start()

    def close_session(self, completed):
        """Write the focus session to the log (a stopped one only if it lasted a while)."""
        if self.mode != "focus" or self.session_start is None:
            return
        done = self.session_total if completed else self.session_total - self.time_left()
        if completed or done >= MIN_LOGGED:
            self.log.append({"t": self.session_start, "end": time.time(), "mode": "focus",
                             "planned": self.session_total, "done": done,
                             "completed": completed})
            self.save()
        self.session_start = None

    def reset(self):
        self.close_session(False)
        self.running = False
        self.remaining = self.length(self.mode)

    def next_mode(self):
        self.close_session(False)
        if self.mode == "focus":
            if self.done > 0 and self.done % self.settings["every"] == 0:
                self.mode = "long"
            else:
                self.mode = "short"
        else:
            self.mode = "focus"
        self.running = False
        self.remaining = self.length(self.mode)

    def finish(self):
        if self.mode == "focus":
            self.done += 1
        self.close_session(True)
        self.flash_until = time.time() + FLASH_TIME
        self.next_mode()

    def update(self):
        if self.running and time.time() >= self.end:
            self.finish()

    def adjust(self, key, delta):
        lo, hi = LIMITS[key]
        old = self.settings[key]
        new = max(lo, min(hi, old + delta))
        if new == old:
            return
        self.settings[key] = new
        self.save()
        # if the timer for this mode has not been touched, show the new length right away
        if (key == self.mode and not self.running and self.session_start is None
                and self.remaining == old * 60):
            self.remaining = self.length(self.mode)

    # ---------- log summary ----------
    def summary(self, days):
        since = midnight(time.time()) - (days - 1) * 86400
        mine = [e for e in self.log if e["t"] >= since]
        sessions = sum(1 for e in mine if e.get("completed"))
        return sessions, sum(e["done"] for e in mine)

    # ---------- input ----------
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    self.press(name)
                    return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # right-click the little clock to start or pause without opening it
            if self.minimized and self.rect and self.rect.collidepoint(event.pos):
                self.toggle_run()
        elif event.type == pygame.MOUSEWHEEL:
            if (self.view == "log" and not self.minimized and self.rect
                    and self.rect.collidepoint(pygame.mouse.get_pos())):
                self.log_scroll -= event.y   # clamped when drawing

    def press(self, name):
        if name == "play":
            self.toggle_run()
        elif name == "skip":
            self.next_mode()
        elif name == "reset":
            self.reset()
        elif name == "set":
            self.view = "settings"
        elif name == "log":
            self.view = "log"
            self.log_scroll = 0
        elif name == "back":
            self.view = "timer"
        elif name == "minimize":
            self.set_minimized(True)
        elif name == "expand":
            self.set_minimized(False)
        elif name.startswith("inc:") or name.startswith("dec:"):
            key = name[4:]
            step = 5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
            self.adjust(key, step if name.startswith("inc:") else -step)

    # ---------- drawing ----------
    def hot_color(self, rect, mouse):
        return SAGE if rect.collidepoint(mouse) else DIM

    def draw_button(self, screen, rect, text, mouse):
        c = self.hot_color(rect, mouse)
        pygame.draw.rect(screen, c, rect, width=1, border_radius=10)
        label = self.small.render(text, True, c)
        screen.blit(label, label.get_rect(center=rect.center))

    def draw(self, screen):
        self.update()
        self.buttons = {}
        if self.minimized:
            self.draw_clock(screen)
            return

        mouse = pygame.mouse.get_pos()
        height = {"timer": 142, "settings": 248, "log": 270}[self.view]
        x = screen.get_width() - self.W - MARGIN
        if CARD_POS == "bottom-right":
            y = screen.get_height() - height - MARGIN
        else:
            y = MARGIN
        self.rect = pygame.Rect(x, y, self.W, height)

        box = pygame.Surface((self.W, height), pygame.SRCALPHA)
        pygame.draw.rect(box, PANEL_BG, box.get_rect(), border_radius=18)
        pygame.draw.rect(box, PANEL_BORDER, box.get_rect(), width=1, border_radius=18)
        screen.blit(box, (x, y))

        # minimize button (top right corner of the card)
        mini = pygame.Rect(x + self.W - 38, y + 8, 28, 24)
        self.buttons["minimize"] = mini
        c = self.hot_color(mini, mouse)
        pygame.draw.rect(screen, c, mini, width=1, border_radius=8)
        pygame.draw.line(screen, c, (mini.centerx - 6, mini.centery + 2),
                         (mini.centerx + 6, mini.centery + 2), 2)

        if self.view == "settings":
            self.draw_settings(screen, x, y, height, mouse)
        elif self.view == "log":
            self.draw_log(screen, x, y, height, mouse)
        else:
            self.draw_timer(screen, x, y, mouse)

    def draw_timer(self, screen, x, y, mouse):
        label_text, color = STYLE[self.mode]
        total = self.length(self.mode)
        left = self.time_left()

        # title (shows "SESSION DONE" for a few seconds after a timer ends)
        if time.time() < self.flash_until:
            title = self.small.render("SESSION DONE", True, CREAM)
        else:
            title = self.small.render(label_text, True, color)
        screen.blit(title, (x + 18, y + 14))

        # session dots: how far you are towards the long break
        every = self.settings["every"]
        filled = every if self.mode == "long" else self.done % every
        for k in range(every):
            cx = x + self.W - 52 - (every - 1 - k) * 16
            if k < filled:
                pygame.draw.circle(screen, SAGE, (cx, y + 20), 5)
            else:
                pygame.draw.circle(screen, FAINT, (cx, y + 20), 5, 1)

        # big time
        minutes, seconds = divmod(int(math.ceil(left)), 60)
        clock = self.big.render("%02d:%02d" % (minutes, seconds), True, CREAM)
        screen.blit(clock, (x + 16, y + 32))

        # progress bar
        bar = pygame.Rect(x + 18, y + 86, self.W - 36, 4)
        pygame.draw.rect(screen, FAINT, bar, border_radius=2)
        frac = 1.0 - (left / total if total else 0)
        if frac > 0:
            fill = pygame.Rect(bar.x, bar.y, max(4, int(bar.w * frac)), bar.h)
            pygame.draw.rect(screen, color, fill, border_radius=2)

        # buttons, spread evenly across the card
        widths = [52, 60, 68, 56, 56]
        gap = (self.W - 36 - sum(widths)) / (len(widths) - 1)
        by = y + 100
        bx = x + 18
        rects = []
        for w in widths:
            rects.append(pygame.Rect(int(bx), by, w, 30))
            bx += w + gap
        play, skip, reset, sett, log = rects
        self.buttons.update({"play": play, "skip": skip, "reset": reset,
                             "set": sett, "log": log})

        c = self.hot_color(play, mouse)
        pygame.draw.rect(screen, c, play, width=1, border_radius=10)
        cx, cy = play.center
        if self.running:
            pygame.draw.rect(screen, c, (cx - 6, cy - 7, 4, 14))
            pygame.draw.rect(screen, c, (cx + 2, cy - 7, 4, 14))
        else:
            pygame.draw.polygon(screen, c, [(cx - 5, cy - 8), (cx - 5, cy + 8), (cx + 8, cy)])

        self.draw_button(screen, skip, "skip", mouse)
        self.draw_button(screen, reset, "reset", mouse)
        self.draw_button(screen, sett, "set", mouse)
        self.draw_button(screen, log, "log", mouse)

    def draw_settings(self, screen, x, y, height, mouse):
        screen.blit(self.small.render("SETTINGS", True, SAGE), (x + 18, y + 14))
        for k, key in enumerate(("focus", "short", "long", "every")):
            ry = y + 44 + k * 38
            screen.blit(self.font.render(LABELS[key], True, CREAM), (x + 18, ry + 5))
            plus = pygame.Rect(x + self.W - 18 - 34, ry, 34, 28)
            value_cx = plus.x - 8 - 40
            minus = pygame.Rect(value_cx - 40 - 8 - 34, ry, 34, 28)
            self.buttons["dec:" + key] = minus
            self.buttons["inc:" + key] = plus
            value = ("%d min" if key != "every" else "%d focus") % self.settings[key]
            surf = self.font.render(value, True, PINK)
            screen.blit(surf, surf.get_rect(center=(value_cx, ry + 14)))
            for rect, sign in ((minus, -1), (plus, 1)):
                c = self.hot_color(rect, mouse)
                pygame.draw.rect(screen, c, rect, width=1, border_radius=9)
                mx, my = rect.center
                pygame.draw.line(screen, c, (mx - 6, my), (mx + 6, my), 2)
                if sign > 0:
                    pygame.draw.line(screen, c, (mx, my - 6), (mx, my + 6), 2)

        back = pygame.Rect(x + 18, y + height - 44, 70, 30)
        self.buttons["back"] = back
        self.draw_button(screen, back, "back", mouse)
        hint = self.small.render("click = 1    shift+click = 5", True, FAINT)
        screen.blit(hint, (back.right + 16, back.centery - hint.get_height() // 2))

    def draw_log(self, screen, x, y, height, mouse):
        screen.blit(self.small.render("LOG", True, SAGE), (x + 18, y + 14))
        n1, t1 = self.summary(1)
        n7, t7 = self.summary(7)
        s1 = "Today: %d session%s, %s focus" % (n1, "" if n1 == 1 else "s", fmt_minutes(t1))
        s7 = "Last 7 days: %d session%s, %s" % (n7, "" if n7 == 1 else "s", fmt_minutes(t7))
        screen.blit(self.small.render(s1, True, CREAM), (x + 18, y + 38))
        screen.blit(self.small.render(s7, True, DIM), (x + 18, y + 58))

        entries = list(reversed(self.log))   # newest first
        max_scroll = max(0, len(entries) - LOG_ROWS)
        self.log_scroll = max(0, min(self.log_scroll, max_scroll))
        top = y + 88
        if not entries:
            screen.blit(self.small.render("No sessions yet. Finish a focus timer to log it.",
                                          True, DIM), (x + 18, top))
        today = midnight(time.time())
        for row, e in enumerate(entries[self.log_scroll:self.log_scroll + LOG_ROWS]):
            ry = top + row * 22
            when = "today" if e["t"] >= today else time.strftime("%b %d", time.localtime(e["t"]))
            clock = time.strftime("%H:%M", time.localtime(e["t"]))
            dur = fmt_minutes(e["done"])
            if e.get("completed"):
                status, color = "completed", SAGE
            else:
                status, color = "stopped", DIM
            screen.blit(self.small.render(when, True, DIM), (x + 18, ry))
            screen.blit(self.small.render(clock, True, CREAM), (x + 82, ry))
            screen.blit(self.small.render(dur, True, CREAM), (x + 140, ry))
            screen.blit(self.small.render(status, True, color), (x + 210, ry))
        if max_scroll > 0:
            more = self.small.render("scroll for more", True, FAINT)
            screen.blit(more, (x + self.W - 52 - more.get_width(), y + 14))

        back = pygame.Rect(x + 18, y + height - 44, 70, 30)
        self.buttons["back"] = back
        self.draw_button(screen, back, "back", mouse)

    # ---------- the minimized cat clock ----------
    def draw_clock(self, screen):
        mouse = pygame.mouse.get_pos()
        R = CLOCK_R
        cx = screen.get_width() - MARGIN - R
        cy = screen.get_height() - MARGIN - R
        # clickable area: the clock plus its ears
        self.rect = pygame.Rect(cx - R - 4, cy - R - 20, 2 * R + 8, 2 * R + 24)
        self.buttons["expand"] = self.rect
        hot = self.rect.collidepoint(mouse)

        now = time.time()
        flashing = now < self.flash_until
        pulse = 0.5 + 0.5 * math.sin(now * 5)
        label_text, color = STYLE[self.mode]
        if flashing:
            color = PINK

        # soft glow ring around the clock while a session has just finished
        if flashing:
            glow = pygame.Surface((2 * R + 40, 2 * R + 40), pygame.SRCALPHA)
            alpha = int(40 + 70 * pulse)
            pygame.draw.circle(glow, PINK + (alpha,), (R + 20, R + 20), R + 10 + int(6 * pulse), 3)
            screen.blit(glow, (cx - R - 20, cy - R - 20))

        # ears
        for side in (-1, 1):
            base_a, base_b, tip_a = (150, 112, 130) if side < 0 else (30, 68, 50)
            outer = [polar(cx, cy, R - 4, base_a), polar(cx, cy, R - 4, base_b),
                     polar(cx, cy, R + 18, tip_a)]
            pygame.draw.polygon(screen, CLOCK_EAR, outer)
            pygame.draw.polygon(screen, CLOCK_EDGE, outer, 2)
            ia, ib, it = (144, 120, 132) if side < 0 else (36, 60, 48)
            inner = [polar(cx, cy, R - 2, ia), polar(cx, cy, R - 2, ib),
                     polar(cx, cy, R + 9, it)]
            pygame.draw.polygon(screen, PINK, inner)

        # body
        pygame.draw.circle(screen, CLOCK_BODY, (cx, cy), R)
        pygame.draw.circle(screen, SAGE if hot else CLOCK_EDGE, (cx, cy), R, 2)

        # progress ring
        ring_r = R - 7
        pygame.draw.circle(screen, FAINT, (cx, cy), ring_r, 4)
        total = self.length(self.mode)
        left = self.time_left()
        frac = 1.0 - (left / total if total else 0)
        if frac > 0:
            steps = max(2, int(120 * frac))
            pts = [polar(cx, cy, ring_r, 90 - 360 * frac * k / steps) for k in range(steps + 1)]
            pygame.draw.lines(screen, color, False, pts, 4)
            pygame.draw.circle(screen, color, (int(pts[0][0]), int(pts[0][1])), 2)
            pygame.draw.circle(screen, color, (int(pts[-1][0]), int(pts[-1][1])), 2)

        # time and a tiny status word
        minutes, seconds = divmod(int(math.ceil(left)), 60)
        t = self.clock_font.render("%02d:%02d" % (minutes, seconds), True, CREAM)
        screen.blit(t, t.get_rect(center=(cx, cy - 3)))
        if flashing:
            word = "done!"
        elif self.running:
            word = "focus" if self.mode == "focus" else "break"
        elif left < total:
            word = "paused"
        else:
            word = "ready"
        w = self.tiny.render(word, True, color if (self.running or flashing) else DIM)
        screen.blit(w, w.get_rect(center=(cx, cy + 13)))