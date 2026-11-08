import time
import pygame
import goals

CREAM = (255, 244, 225)
SAGE = (150, 185, 165)
PINK = (225, 170, 190)
DIM = (125, 135, 160)
FAINT = (60, 68, 100)
RED = (225, 130, 140)
PANEL_BG = (14, 17, 32, 215)
PANEL_BORDER = (70, 80, 115, 160)
FIELD_BG = (24, 28, 50)

SORT_DELAY = 1.0   # seconds after a tick before finished goals sink to the bottom
DRAG_START = 6     # pixels you must move while holding before a drag begins


class Panel:
    def __init__(self):
        self.data = goals.load()
        goals.auto_sort(self.data)
        self.open = False
        self.mode = "list"  # "list" or "add" (the form is used for add and edit)
        self.big = pygame.font.Font(None, 40)
        self.font = pygame.font.Font(None, 30)
        self.small = pygame.font.Font(None, 22)
        self.msg = ""
        self.msg_time = 0
        self.x = 30
        self.y = 100
        self.w = 720
        self.row_h = 46
        self.scroll = 0.0
        self.max_rows = 8
        self.hits = []        # (what, goal number, rect) for everything clickable in the list
        self.add_rect = None
        self.confirm = None   # goal waiting for a second click to delete
        # drag and drop
        self.press = None     # {"i": row index, "pos": where the mouse went down}
        self.dragging = False
        # auto-sort (finished goals sink to the bottom shortly after you tick them)
        self.sort_due = 0.0
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
                self.press = None
                self.dragging = False
                if self.open:
                    self.data = goals.load()
                    goals.auto_sort(self.data)
        elif event.type == pygame.MOUSEWHEEL:
            if self.open and self.mode == "list":
                self.scroll -= event.y * 0.35
        elif event.type == pygame.MOUSEBUTTONDOWN and self.open:
            if self.mode == "add":
                if event.button == 1:
                    self.click_form(event.pos)
            elif event.button == 1:
                self.click_list(event.pos)
            elif event.button == 3:
                self.right_click(event.pos)

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
            self.sort_due = time.time() + SORT_DELAY
        else:
            goals.add_goal(self.data, name, stars, self.kind)
            goals.auto_sort(self.data)
            # jump to the new goal (it is the last unfinished one)
            last_open = max(i for i, g in enumerate(self.data["goals"]) if not goals.is_done(g))
            self.scroll = float(last_open - self.max_rows + 1)
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

    def say(self, text):
        self.msg = text
        self.msg_time = time.time()

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

        # buttons first
        for what, i, rect in self.hits:
            if what == "row" or not rect.collidepoint(pos):
                continue
            if what == "del":
                if self.confirm == i:
                    goals.delete_goal(self.data, i)
                    self.confirm = None
                else:
                    self.confirm = i  # first click asks "sure?"
                return
            self.confirm = None
            if what == "edit":
                g = self.data["goals"][i]
                self.mode = "add"
                self.edit_index = i
                self.name = g["name"]
                self.stars_text = str(g["stars"])
                self.kind = g["kind"]
                self.field = 0
            elif what == "plus":
                earned = goals.tick(self.data, i)
                if earned:
                    self.say("+" + str(earned) + " stars")
                self.sort_due = time.time() + SORT_DELAY
            elif what == "minus":
                removed = goals.untick(self.data, i)
                if removed:
                    self.say("-" + str(removed) + " stars")
                self.sort_due = time.time() + SORT_DELAY
            return

        # then the row itself: remember the press. If the mouse moves it becomes a
        # drag, if it is let go in place it counts as a click (see update_drag)
        self.confirm = None
        for what, i, rect in self.hits:
            if what == "row" and rect.collidepoint(pos):
                self.press = {"i": i, "pos": pos}
                self.dragging = False
                return

    def row_clicked(self, i):
        goal = self.data["goals"][i]
        if goal["kind"] == "once":
            if goals.can_tick(goal):
                earned = goals.tick(self.data, i)
                self.say("+" + str(earned) + " stars")
            else:
                removed = goals.untick(self.data, i)
                self.say("-" + str(removed) + " stars")
        elif goals.today_count(goal) == 0:
            earned = goals.tick(self.data, i)  # first tick = "add to cart"
            self.say("+" + str(earned) + " stars")
        # daily goal that is already ticked: use the - / + buttons
        self.sort_due = time.time() + SORT_DELAY

    def right_click(self, pos):
        # right-click a row to undo one tick
        for what, i, rect in self.hits:
            if what == "row" and rect.collidepoint(pos):
                removed = goals.untick(self.data, i)
                if removed:
                    self.say("-" + str(removed) + " stars")
                self.sort_due = time.time() + SORT_DELAY
                return

    def update_drag(self, first, rows_shown, list_top):
        """Called every frame from draw_list. Handles hold-and-drag reordering."""
        if self.press is None:
            return
        mx, my = pygame.mouse.get_pos()
        if not pygame.mouse.get_pressed()[0]:
            # mouse released
            if self.dragging:
                goals.save(self.data)
                self.sort_due = time.time() + SORT_DELAY
            else:
                self.row_clicked(self.press["i"])
            self.press = None
            self.dragging = False
            return

        if not self.dragging and abs(my - self.press["pos"][1]) > DRAG_START:
            self.dragging = True
            self.confirm = None
        if not self.dragging:
            return

        # the row under the mouse is where the dragged goal should go
        slot = int((my - list_top) // self.row_h)
        target = max(first, min(first + rows_shown - 1, first + slot))
        if target != self.press["i"]:
            goals.move_to(self.data, self.press["i"], target)
            self.press["i"] = target

        # scroll while dragging near the top or bottom edge
        if my < list_top + 8:
            self.scroll -= 0.12
        elif my > list_top + rows_shown * self.row_h - 8:
            self.scroll += 0.12

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

    def draw_grip(self, screen, x, cy, color):
        for dx in (0, 6):
            for dy in (-8, 0, 8):
                pygame.draw.circle(screen, color, (x + dx, cy + dy), 2)

    def draw_list(self, screen):
        # finished goals sink to the bottom a moment after you tick them
        if self.sort_due and time.time() >= self.sort_due and self.press is None:
            self.sort_due = 0.0
            if goals.auto_sort(self.data):
                self.confirm = None

        goal_list = self.data["goals"]
        top = 60
        bottom = 90

        # how many rows fit on this screen
        space = screen.get_height() - self.y - top - bottom - 20
        max_rows = max(3, space // self.row_h)
        self.max_rows = max_rows
        rows_shown = min(len(goal_list), max_rows)
        max_scroll = max(0, len(goal_list) - max_rows)
        self.scroll = max(0.0, min(self.scroll, float(max_scroll)))
        first = int(self.scroll)

        self.update_drag(first, rows_shown, self.y + top)
        self.scroll = max(0.0, min(self.scroll, float(max_scroll)))
        first = int(self.scroll)
        goal_list = self.data["goals"]

        rows = max(1, rows_shown)
        height = top + rows * self.row_h + bottom
        self.draw_box(screen, height)
        mouse = pygame.mouse.get_pos()
        screen.blit(self.font.render("My goals", True, SAGE), (self.x + 22, self.y + 18))

        if max_scroll > 0:
            more = self.small.render("scroll for more", True, DIM)
            screen.blit(more, (self.x + self.w - more.get_width() - 24, self.y + 24))

        self.hits = []

        if not goal_list:
            empty = self.small.render("No goals yet. Click + Add goal below", True, DIM)
            screen.blit(empty, (self.x + 22, self.y + 76))

        for slot in range(rows_shown):
            i = first + slot
            g = goal_list[i]
            y = self.y + top + slot * self.row_h
            rect = pygame.Rect(self.x + 12, y, self.w - 24, self.row_h - 6)
            h = rect.height

            del_rect = pygame.Rect(rect.right - 44, y, 44, h)
            edit_rect = pygame.Rect(del_rect.x - 54, y, 54, h)
            stepper_rect = pygame.Rect(edit_rect.x - 8 - 104, y + (h - 32) // 2, 104, 32)
            daily = g["kind"] == "daily"
            count = goals.today_count(g)
            done = count > 0
            dragged = self.dragging and self.press is not None and self.press["i"] == i

            self.hits.append(("row", i, rect))
            self.hits.append(("del", i, del_rect))
            self.hits.append(("edit", i, edit_rect))

            # columns, going left from the stepper
            kind_text = self.small.render("daily" if daily else "once", True, DIM)
            kind_x = stepper_rect.x - 10 - kind_text.get_width()
            word = "star" if g["stars"] == 1 else "stars"
            stars_text = self.small.render(str(g["stars"]) + " " + word, True,
                                           DIM if (done and not daily) else PINK)
            stars_x = kind_x - 14 - stars_text.get_width()

            on_buttons = (del_rect.collidepoint(mouse) or edit_rect.collidepoint(mouse)
                          or (daily and stepper_rect.collidepoint(mouse)))
            if dragged:
                lift = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(lift, (255, 255, 255, 34), lift.get_rect(), border_radius=10)
                screen.blit(lift, rect.topleft)
                pygame.draw.rect(screen, SAGE, rect, width=1, border_radius=10)
            elif rect.collidepoint(mouse) and not on_buttons and not self.dragging:
                hover = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(hover, (255, 255, 255, 18), hover.get_rect(), border_radius=10)
                screen.blit(hover, rect.topleft)

            # grip (hold and drag the row to move it)
            self.draw_grip(screen, rect.x + 10, rect.centery,
                           SAGE if dragged else FAINT)

            # circle
            circle = (rect.x + 38, rect.centery)
            if done:
                pygame.draw.circle(screen, SAGE, circle, 9)
            else:
                pygame.draw.circle(screen, CREAM, circle, 9, 2)

            # name (clipped so it never runs into the other columns)
            name = self.font.render(g["name"], True, DIM if done else CREAM)
            name_x = rect.x + 60
            screen.set_clip(pygame.Rect(name_x, y, max(0, stars_x - 10 - name_x), h))
            screen.blit(name, (name_x, rect.centery - name.get_height() // 2))
            screen.set_clip(None)

            # stars and kind
            screen.blit(stars_text, (stars_x, rect.centery - stars_text.get_height() // 2))
            screen.blit(kind_text, (kind_x, rect.centery - kind_text.get_height() // 2))

            # stepper: "Add" first, then - count + (daily goals only)
            if daily:
                if count == 0:
                    self.hits.append(("plus", i, stepper_rect))
                    hot = stepper_rect.collidepoint(mouse)
                    pygame.draw.rect(screen, SAGE if hot else DIM, stepper_rect,
                                     width=1, border_radius=10)
                    lab = self.small.render("Add", True, SAGE if hot else DIM)
                    screen.blit(lab, lab.get_rect(center=stepper_rect.center))
                else:
                    minus_rect = pygame.Rect(stepper_rect.x, stepper_rect.y, 32, 32)
                    plus_rect = pygame.Rect(stepper_rect.right - 32, stepper_rect.y, 32, 32)
                    self.hits.append(("minus", i, minus_rect))
                    self.hits.append(("plus", i, plus_rect))
                    pygame.draw.rect(screen, FIELD_BG, stepper_rect, border_radius=10)
                    pygame.draw.rect(screen, SAGE, stepper_rect, width=1, border_radius=10)
                    num = self.font.render(str(count), True, CREAM)
                    screen.blit(num, num.get_rect(center=stepper_rect.center))
                    mc = SAGE if minus_rect.collidepoint(mouse) else DIM
                    pc = SAGE if plus_rect.collidepoint(mouse) else DIM
                    cx, cy = minus_rect.center
                    pygame.draw.line(screen, mc, (cx - 6, cy), (cx + 6, cy), 2)
                    cx, cy = plus_rect.center
                    pygame.draw.line(screen, pc, (cx - 6, cy), (cx + 6, cy), 2)
                    pygame.draw.line(screen, pc, (cx, cy - 6), (cx, cy + 6), 2)

            # edit, delete
            edit_color = SAGE if edit_rect.collidepoint(mouse) else DIM
            edit_label = self.small.render("edit", True, edit_color)
            screen.blit(edit_label, edit_label.get_rect(center=edit_rect.center))
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
            pygame.draw.rect(screen, FAINT,
                             (self.x + self.w - 8, thumb_y, 3, thumb_h), border_radius=2)

        # add button and a small hint
        self.add_rect = pygame.Rect(self.x + 12, self.y + top + rows * self.row_h + 4,
                                    self.w - 24, 40)
        if self.add_rect.collidepoint(mouse):
            hover = pygame.Surface(self.add_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(hover, (255, 255, 255, 18), hover.get_rect(), border_radius=10)
            screen.blit(hover, self.add_rect.topleft)
        pygame.draw.rect(screen, SAGE, self.add_rect, width=1, border_radius=10)
        label = self.font.render("+ Add goal", True, SAGE)
        screen.blit(label, label.get_rect(center=self.add_rect.center))
        tip = self.small.render("click = tick    hold and drag = move    right-click = undo one",
                                True, FAINT)
        screen.blit(tip, (self.x + 24, self.add_rect.bottom + 10))

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
            text = "Repeats every day, tick it as many times as you want  (click to change)"
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