import json
import os
import time
import pygame
import goals

CREAM = (255, 244, 225)
SAGE = (150, 185, 165)
PINK = (225, 170, 190)
DIM = (125, 135, 160)
FAINT = (60, 68, 100)
PANEL_BG = (14, 17, 32, 225)
PANEL_BORDER = (70, 80, 115, 160)

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "journal.json")   # your journal lives here (keep it private)

ROW_H = 26


def load():
    try:
        with open(FILE) as f:
            data = json.load(f)
        return [e for e in data if "t" in e and "name" in e and "stars" in e]
    except (OSError, ValueError):
        return []


class Journal:
    W = 520

    def __init__(self):
        self.entries = load()
        self.open = False
        self.scroll = 0
        self.rect = None
        self.big = pygame.font.Font(None, 30)
        self.font = pygame.font.Font(None, 26)
        self.small = pygame.font.Font(None, 22)
        self.install()

    # ---------- recording ----------
    def install(self):
        """Wrap goals.tick and goals.untick, so every tick is written to the journal."""
        if getattr(goals, "_journal_installed", False):
            return
        goals._journal_installed = True
        orig_tick = goals.tick
        orig_untick = goals.untick
        journal = self

        def tick(data, index):
            g = data["goals"][index]
            name, kind = g["name"], g.get("kind", "daily")
            earned = orig_tick(data, index)
            if earned:
                journal.add(name, earned, kind)
            return earned

        def untick(data, index):
            name = data["goals"][index]["name"]
            removed = orig_untick(data, index)
            if removed:
                journal.remove_last(name)
            return removed

        goals.tick = tick
        goals.untick = untick

    def save(self):
        try:
            with open(FILE, "w") as f:
                json.dump(self.entries, f, indent=1)
        except OSError:
            pass

    def add(self, name, stars, kind):
        self.entries.append({"t": time.time(), "name": name, "stars": stars, "kind": kind})
        self.save()

    def remove_last(self, name):
        for i in range(len(self.entries) - 1, -1, -1):
            if self.entries[i]["name"] == name:
                del self.entries[i]
                self.save()
                return

    # ---------- input ----------
    def toggle(self):
        self.open = not self.open
        self.scroll = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.open and self.rect:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll -= event.y * 2

    # ---------- drawing ----------
    def day_label(self, ts):
        d = time.strftime("%Y-%m-%d", time.localtime(ts))
        nice = time.strftime("%a %d %b", time.localtime(ts))
        if d == time.strftime("%Y-%m-%d"):
            return "Today, " + nice
        if d == time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400)):
            return "Yesterday, " + nice
        return nice

    def build_lines(self):
        days = {}
        for e in self.entries:
            key = time.strftime("%Y-%m-%d", time.localtime(e["t"]))
            days.setdefault(key, []).append(e)
        lines = []
        for key in sorted(days, reverse=True):
            items = sorted(days[key], key=lambda e: e["t"])
            stars = sum(e["stars"] for e in items)
            lines.append(("day", self.day_label(items[0]["t"]), len(items), stars))
            for e in items:
                lines.append(("tick", time.strftime("%H:%M", time.localtime(e["t"])),
                              e["name"], e["stars"]))
        return lines

    def draw(self, screen):
        if not self.open:
            self.rect = None
            return
        sw, sh = screen.get_size()
        h = min(sh - 140, 640)
        x = (sw - self.W) // 2
        y = 90
        self.rect = pygame.Rect(x, y, self.W, h)

        box = pygame.Surface((self.W, h), pygame.SRCALPHA)
        pygame.draw.rect(box, PANEL_BG, box.get_rect(), border_radius=18)
        pygame.draw.rect(box, PANEL_BORDER, box.get_rect(), width=1, border_radius=18)
        screen.blit(box, (x, y))

        screen.blit(self.big.render("Journal", True, SAGE), (x + 22, y + 16))
        close = self.small.render("press J to close", True, FAINT)
        screen.blit(close, (x + self.W - close.get_width() - 22, y + 22))

        # today's summary
        today_key = time.strftime("%Y-%m-%d")
        todays = [e for e in self.entries
                  if time.strftime("%Y-%m-%d", time.localtime(e["t"])) == today_key]
        if todays:
            total = sum(e["stars"] for e in todays)
            summary = "Today: %d tick%s, %d star%s" % (
                len(todays), "" if len(todays) == 1 else "s",
                total, "" if total == 1 else "s")
            color = CREAM
        else:
            summary = "Nothing ticked today yet."
            color = DIM
        screen.blit(self.small.render(summary, True, color), (x + 22, y + 50))

        lines = self.build_lines()
        top = y + 84
        rows = (h - 84 - 18) // ROW_H
        max_scroll = max(0, len(lines) - rows)
        self.scroll = max(0, min(self.scroll, max_scroll))

        if not lines:
            msg = self.small.render("Nothing here yet. Tick a goal and it shows up.", True, DIM)
            screen.blit(msg, (x + 22, top + 6))

        for n, line in enumerate(lines[self.scroll:self.scroll + rows]):
            ry = top + n * ROW_H
            if line[0] == "day":
                if n > 0:
                    pygame.draw.line(screen, FAINT, (x + 20, ry + 2), (x + self.W - 20, ry + 2))
                label = self.font.render(line[1], True, SAGE)
                screen.blit(label, (x + 22, ry + 6))
                info = self.small.render(
                    "%d tick%s, %d star%s" % (line[2], "" if line[2] == 1 else "s",
                                              line[3], "" if line[3] == 1 else "s"),
                    True, DIM)
                screen.blit(info, (x + self.W - info.get_width() - 24, ry + 9))
            else:
                _, when, name, stars = line
                screen.blit(self.small.render(when, True, DIM), (x + 30, ry + 6))
                stars_text = self.small.render("+%d" % stars, True, PINK)
                stars_x = x + self.W - stars_text.get_width() - 28
                screen.blit(stars_text, (stars_x, ry + 6))
                name_x = x + 94
                screen.set_clip(pygame.Rect(name_x, ry, max(0, stars_x - name_x - 10), ROW_H))
                screen.blit(self.font.render(name, True, CREAM), (name_x, ry + 4))
                screen.set_clip(None)

        if max_scroll > 0:
            track_h = rows * ROW_H
            thumb_h = max(24, int(track_h * rows / len(lines)))
            thumb_y = top + int((track_h - thumb_h) * (self.scroll / max_scroll))
            pygame.draw.rect(screen, FAINT, (x + self.W - 9, thumb_y, 3, thumb_h), border_radius=2)