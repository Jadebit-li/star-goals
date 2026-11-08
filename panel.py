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
        self.mode = "list"  # "list" or "add" (the form is used for add and edit)
        self.big = pygame.font.Font(None, 40)
        self.font = pygame.font.Font(None, 30)
        self.small = pygame.font.Font(None, 22)
        self.msg = ""
        self.msg_time = 0
        self.x = 30
        self.y = 100
        self.w = 580
        self.row_h = 46
        self.scroll = 0.0
        self.rects = []       # (goal number, rect) for the rows on screen
        self.del_rects = []   # (goal number, rect) for the x buttons
        self.edit_rects = []  # (goal number, rect) for the edit buttons
        self.add_rect = None
        self.confirm = None   # goal waiting for a second click to delete
        # goal form
        self.edit_index = None  # None = adding a new goal, a number = editing that goal
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
                self.edit_index = None
                self.confirm = None
                if self.open:
                    self.data = goals.load()
        elif event.type == pygame.MOUSEWHEEL:
            if self.open and self.mode == "list":
                self.scroll -= event.y * 0.35
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.open:
            if self.mode == "add":
                self.click_form(event.pos)
            else:
                self.click_list(event.pos)

    def close_form(self):
        self.mode = "list"
        self.edit_index = None

    def key_in_form(self, event):
        if event.key == pygame.K_ESCAPE:
            self.close_form()
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
        stars = max(1, int(self.stars_text))
        if self.edit_index is not None:
            goals.edit_goal(self.data, self.edit_index, name, stars, self.kind)
        else:
            goals.add_goal(self.data, name, stars, self.kind)
            self.scroll = 10 ** 6  # jump to the bottom so you see the new goal
        self.close_form()

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
            self.close_form()

    def click_list(self, pos):
        if self.add_rect and self.add_rect.collidepoint(pos):
            self.mode = "add"
            self.edit_index = None
            self.name = ""
            self.stars_text = "1"
            self.kind = "daily"
            self.field = 0
            self.confirm = None
            return
        for i, rect in self.del_rects:
            if rect.collidepoint(pos):
                if self.confirm == i:
                    goals.delete_goal(self.data, i)
                    self.confirm = None
                else:
                    self.confirm = i  # first click asks "sure?"
                return
        for i, rect in self.edit_rects:
            if rect.collidepoint(pos):
                g = self.data["goals"][i]
                self.mode = "add"
                self.edit_index = i
                self.name = g["name"]
                self.stars_text = str(g["stars"])
                self.kind = g["kind"]
                self.field = 0
                self.confirm = None
                return
        self.confirm = None
        for i, rect in self.rects:
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
        top = 60

        # how many rows fit on this screen
        space = screen.get_height() - self.y - top - 60 - 30
        max_rows = max(3, space // self.row_h)
        rows_shown = min(len(goal_list), max_rows)
        max_scroll = max(0, len(goal_list) - max_rows)
        self.scroll = max(0.0, min(self.scroll, float(max_scroll)))
        first = int(self.scroll)

        rows = max(1, rows_shown)
        height = top + rows * self.row_h + 60
        self.draw_box(screen, height)
        screen.blit(self.font.render("My goals", True, SAGE), (self.x + 22, self.y + 18))
        if max_scroll > 0:
            more = self.small.render("scroll for more", True, DIM)
            screen.blit(more, (self.x + self.w - more.get_width() - 24, self.y + 24))

        self.rects = []
        self.del_rects = []
        self.edit_rects = []
        mouse = pygame.mouse.get_pos()

        if not goal_list:
            empty = self.small.render("No goals yet. Click + Add goal below", True, DIM)
            screen.blit(empty, (self.x + 22, self.y + 76))

        for slot in range(rows_shown):
            i = first + slot
            g = goal_list[i]
            rect = pygame.Rect(self.x + 12, self.y + top + slot * self.row_h,
                               self.w - 24, self.row_h - 6)
            del_rect = pygame.Rect(rect.right - 50, rect.y, 50, rect.height)
            edit_rect = pygame.Rect(del_rect.x - 56, rect.y, 56, rect.height)
            self.rects.append((i, rect))
            self.del_rects.append((i, del_rect))
            self.edit_rects.append((i, edit_rect))
            done = not goals.can_tick(g)

            on_buttons = del_rect.collidepoint(mouse) or edit_rect.collidepoint(mouse)
            if rect.collidepoint(mouse) and not on_buttons and not done:
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

            # "daily" or "once" label, then the stars, going left from the edit button
            kind_text = self.small.render("daily" if g["kind"] == "daily" else "once", True, DIM)
            kind_x = edit_rect.x - kind_text.get_width() - 6
            screen.blit(kind_text, (kind_x, rect.centery - kind_text.get_height() // 2))
            word = "star" if g["stars"] == 1 else "stars"
            stars = self.small.render(str(g["stars"]) + " " + word, True, DIM if done else PINK)
            screen.blit(stars, (kind_x - stars.get_width() - 14,
                                rect.centery - stars.get_height() // 2))

            # edit button
            edit_color = SAGE if edit_rect.collidepoint(mouse) else DIM
            edit_label = self.small.render("edit", True, edit_color)
            screen.blit(edit_label, edit_label.get_rect(center=edit_rect.center))

            # delete button
            if self.confirm == i:
                label = self.small.render("sure?", True, RED)
            else:
                label = self.small.render("x", True, DIM)
            screen.blit(label, label.get_rect(center=del_rect.center))

        # thin scroll bar
        if max_scroll > 0:
            track_y = self.y + top
            track_h = rows * self.row_h - 6
            thumb_h = max(24, int(track_h * max_rows / len(goal_list)))
            thumb_y = track_y + int((track_h - thumb_h) * (self.scroll / max_scroll))
            pygame.draw.rect(screen, (60, 68, 100),
                             (self.x + self.w - 8, thumb_y, 3, thumb_h), border_radius=2)

        # add button
        self.add_rect = pygame.Rect(self.x + 12, self.y + top + rows * self.row_h + 4,
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
        title = "Edit goal" if self.edit_index is not None else "New goal"
        screen.blit(self.font.render(title, True, SAGE), (self.x + 22, self.y + 18))

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

        save_rect = pygame.Rect(self.x + 22, self.y + 284, 210, 46)
        cancel_rect = pygame.Rect(self.x + self.w - 22 - 210, self.y + 284, 210, 46)
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