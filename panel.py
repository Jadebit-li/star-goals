import time
import pygame
import goals

CREAM = (255, 244, 225)
SAGE = (150, 185, 165)
PINK = (225, 170, 190)
DIM = (125, 135, 160)
RED = (225, 130, 140)
PANEL_BG = (14, 17, 32, 215)
PANEL_BORDER = (70, 80, 115, 160)
FIELD_BG = (24, 28, 50)


class Panel:
    def __init__(self):
        self.data = goals.load()
        self.open = False
        self.mode = "list"  # "list" or "add"
        self.big = pygame.font.Font(None, 40)
        self.font = pygame.font.Font(None, 30)
        self.small = pygame.font.Font(None, 22)
        self.msg = ""
        self.msg_time = 0
        self.x = 30
        self.y = 100
        self.w = 480
        self.row_h = 46
        self.rects = []
        self.del_rects = []
        self.add_rect = None
        self.confirm = None  # goal waiting for a second click to delete
        # add-goal form
        self.name = ""
        self.stars_text = "1"
        self.kind = "daily"
        self.field = 0  # 0 = name box, 1 = stars box
        self.form_rects = {}

    @property
    def typing(self):
        # sky.py checks this, so typing a name does not trigger hotkeys
        return self.open and self.mode == "add"

    # ---------- input ----------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.typing:
                self.key_in_form(event)
                return
            if event.key == pygame.K_g:
                self.open = not self.open
                self.mode = "list"
                self.confirm = None
                if self.open:
                    self.data = goals.load()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.open:
            if self.mode == "add":
                self.click_form(event.pos)
            else:
                self.click_list(event.pos)

    def key_in_form(self, event):
        if event.key == pygame.K_ESCAPE:
            self.mode = "list"
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.save_form()
        elif event.key == pygame.K_TAB:
            self.field = 1 - self.field
        elif event.key == pygame.K_BACKSPACE:
            if self.field == 0:
                self.name = self.name[:-1]
            else:
                self.stars_text = self.stars_text[:-1]
        elif event.unicode and event.unicode.isprintable():
            if self.field == 0:
                if len(self.name) < 22:
                    self.name += event.unicode
            elif event.unicode.isdigit() and len(self.stars_text) < 3:
                self.stars_text += event.unicode

    def save_form(self):
        name = self.name.strip()
        if not name or not self.stars_text:
            return
        goals.add_goal(self.data, name, max(1, int(self.stars_text)), self.kind)
        self.mode = "list"

    def click_form(self, pos):
        r = self.form_rects
        if r["name"].collidepoint(pos):
            self.field = 0
        elif r["stars"].collidepoint(pos):
            self.field = 1
        elif r["kind"].collidepoint(pos):
            self.kind = "once" if self.kind == "daily" else "daily"
        elif r["save"].collidepoint(pos):
            self.save_form()
        elif r["cancel"].collidepoint(pos):
            self.mode = "list"

    def click_list(self, pos):
        if self.add_rect and self.add_rect.collidepoint(pos):
            self.mode = "add"
            self.name = ""
            self.stars_text = "1"
            self.kind = "daily"
            self.field = 0
            self.confirm = None
            return
        for i, rect in enumerate(self.del_rects):
            if rect.collidepoint(pos):
                if self.confirm == i:
                    goals.delete_goal(self.data, i)
                    self.confirm = None
                else:
                    self.confirm = i  # first click asks "sure?"
                return
        self.confirm = None
        for i, rect in enumerate(self.rects):
            if rect.collidepoint(pos):
                goal = self.data["goals"][i]
                if goals.can_tick(goal):
                    earned = goals.tick(self.data, i)
                    self.msg = "+" + str(earned) + " stars"
                else:
                    removed = goals.untick(self.data, i)
                    self.msg = "-" + str(removed) + " stars"
                self.msg_time = time.time()

    # ---------- drawing ----------
    def draw_box(self, screen, height):
        box = pygame.Surface((self.w, height), pygame.SRCALPHA)
        pygame.draw.rect(box, PANEL_BG, box.get_rect(), border_radius=18)
        pygame.draw.rect(box, PANEL_BORDER, box.get_rect(), width=1, border_radius=18)
        screen.blit(box, (self.x, self.y))

    def draw_field(self, screen, rect, text, focused):
        pygame.draw.rect(screen, FIELD_BG, rect, border_radius=10)
        pygame.draw.rect(screen, SAGE if focused else DIM, rect, width=1, border_radius=10)
        cursor = "|" if focused and int(time.time() * 2) % 2 == 0 else ""
        surf = self.font.render(text + cursor, True, CREAM)
        screen.blit(surf, (rect.x + 14, rect.centery - surf.get_height() // 2))

    def draw(self, screen):
        # star counter (always visible)
        total = self.big.render(str(self.data["total_stars"]) + " stars", True, CREAM)
        screen.blit(total, (self.x, 34))
        if not self.open:
            hint = self.small.render("press G for goals", True, DIM)
            screen.blit(hint, (self.x, 70))

        # "+2 stars" message that fades out
        age = time.time() - self.msg_time
        if self.msg and age < 2.5:
            text = self.font.render(self.msg, True, PINK)
            text.set_alpha(int(255 * (1 - age / 2.5)))
            screen.blit(text, (self.x + total.get_width() + 20, 40))

        if not self.open:
            return
        if self.mode == "add":
            self.draw_form(screen)
        else:
            self.draw_list(screen)

    def draw_list(self, screen):
        goal_list = self.data["goals"]
        rows = max(1, len(goal_list))
        height = 66 + rows * self.row_h + 60
        self.draw_box(screen, height)
        screen.blit(self.font.render("My goals", True, SAGE), (self.x + 22, self.y + 18))

        self.rects = []
        self.del_rects = []
        mouse = pygame.mouse.get_pos()

        if not goal_list:
            empty = self.small.render("No goals yet. Click + Add goal below", True, DIM)
            screen.blit(empty, (self.x + 22, self.y + 76))

        for i, g in enumerate(goal_list):
            rect = pygame.Rect(self.x + 12, self.y + 60 + i * self.row_h,
                               self.w - 24, self.row_h - 6)
            del_rect = pygame.Rect(rect.right - 60, rect.y, 60, rect.height)
            self.rects.append(rect)
            self.del_rects.append(del_rect)
            done = not goals.can_tick(g)

            if rect.collidepoint(mouse) and not del_rect.collidepoint(mouse) and not done:
                hover = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(hover, (255, 255, 255, 18), hover.get_rect(), border_radius=10)
                screen.blit(hover, rect.topleft)

            circle = (rect.x + 18, rect.centery)
            if done:
                pygame.draw.circle(screen, SAGE, circle, 9)
            else:
                pygame.draw.circle(screen, CREAM, circle, 9, 2)

            name = self.font.render(g["name"], True, DIM if done else CREAM)
            screen.blit(name, (rect.x + 40, rect.centery - name.get_height() // 2))

            stars = self.small.render(str(g["stars"]) + " stars", True, DIM if done else PINK)
            screen.blit(stars, (del_rect.x - stars.get_width() - 6,
                                rect.centery - stars.get_height() // 2))

            if self.confirm == i:
                label = self.small.render("sure?", True, RED)
            else:
                label = self.small.render("x", True, DIM)
            screen.blit(label, label.get_rect(center=del_rect.center))

        # add button
        self.add_rect = pygame.Rect(self.x + 12, self.y + 60 + rows * self.row_h + 4,
                                    self.w - 24, 40)
        if self.add_rect.collidepoint(mouse):
            hover = pygame.Surface(self.add_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(hover, (255, 255, 255, 18), hover.get_rect(), border_radius=10)
            screen.blit(hover, self.add_rect.topleft)
        pygame.draw.rect(screen, SAGE, self.add_rect, width=1, border_radius=10)
        label = self.font.render("+ Add goal", True, SAGE)
        screen.blit(label, label.get_rect(center=self.add_rect.center))

    def draw_form(self, screen):
        self.draw_box(screen, 362)
        screen.blit(self.font.render("New goal", True, SAGE), (self.x + 22, self.y + 18))

        screen.blit(self.small.render("Name", True, DIM), (self.x + 24, self.y + 60))
        name_rect = pygame.Rect(self.x + 22, self.y + 82, self.w - 44, 42)
        self.draw_field(screen, name_rect, self.name, self.field == 0)

        screen.blit(self.small.render("Stars you get", True, DIM), (self.x + 24, self.y + 140))
        stars_rect = pygame.Rect(self.x + 22, self.y + 162, 120, 42)
        self.draw_field(screen, stars_rect, self.stars_text, self.field == 1)

        kind_rect = pygame.Rect(self.x + 22, self.y + 222, self.w - 44, 42)
        pygame.draw.rect(screen, FIELD_BG, kind_rect, border_radius=10)
        pygame.draw.rect(screen, DIM, kind_rect, width=1, border_radius=10)
        if self.kind == "daily":
            text = "Repeats every day  (click to change)"
        else:
            text = "One time only  (click to change)"
        label = self.small.render(text, True, CREAM)
        screen.blit(label, (kind_rect.x + 14, kind_rect.centery - label.get_height() // 2))

        save_rect = pygame.Rect(self.x + 22, self.y + 284, 200, 46)
        cancel_rect = pygame.Rect(self.x + self.w - 22 - 200, self.y + 284, 200, 46)
        pygame.draw.rect(screen, (55, 85, 70), save_rect, border_radius=12)
        pygame.draw.rect(screen, SAGE, save_rect, width=1, border_radius=12)
        pygame.draw.rect(screen, FIELD_BG, cancel_rect, border_radius=12)
        pygame.draw.rect(screen, DIM, cancel_rect, width=1, border_radius=12)
        save_label = self.font.render("Save", True, CREAM)
        cancel_label = self.font.render("Cancel", True, DIM)
        screen.blit(save_label, save_label.get_rect(center=save_rect.center))
        screen.blit(cancel_label, cancel_label.get_rect(center=cancel_rect.center))

        hint = self.small.render("Tab = next box    Enter = save    Esc = cancel", True, DIM)
        screen.blit(hint, (self.x + 24, self.y + 338))

        self.form_rects = {
            "name": name_rect, "stars": stars_rect, "kind": kind_rect,
            "save": save_rect, "cancel": cancel_rect,
        }