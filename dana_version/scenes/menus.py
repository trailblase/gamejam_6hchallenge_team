"""Title, team select and leader select. Keyboard (arrows + Enter, Esc to go
back) with optional mouse."""

import math

import pygame

from data import config
from data.characters import CHARACTERS, PRESET_TEAMS
from ui import draw as D
from ui import sprites as S
from ui.character_sprites import draw_character
from ui.topdown_assets import draw_menu_backdrop

W, H = config.WINDOW_W, config.WINDOW_H
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)


def menu_background(screen, t):
    if D.CURRENT_STYLE == "medieval":
        draw_menu_backdrop(screen, t)
        return
    screen.fill(D.PALETTE["cream"])
    blobs = [("sage_light", 0.12, 0.2, 140), ("peach", 0.85, 0.25, 120), ("blue_light", 0.2, 0.85, 160),
             ("pink", 0.8, 0.8, 130), ("lavender", 0.5, 0.05, 90)]
    for i, (col, fx, fy, r) in enumerate(blobs):
        x = fx * W + math.sin(t * 0.4 + i) * 18
        y = fy * H + math.cos(t * 0.33 + i * 2) * 14
        pygame.draw.circle(screen, D.mix(D.PALETTE[col], D.PALETTE["cream"], 0.35), (x, y), r)


def card_row_rects(count, card_w, card_h, top):
    gap = 28
    total = card_w * count + gap * (count - 1)
    x0 = (W - total) // 2
    return [pygame.Rect(x0 + i * (card_w + gap), top, card_w, card_h) for i in range(count)]


class _CardMenu:
    """Shared keyboard/mouse handling for a row of selectable cards."""

    def __init__(self, app, count):
        self.app = app
        self.count = count
        self.index = 0
        self.t = 0.0

    def rects(self):
        raise NotImplementedError

    def confirm(self, index):
        raise NotImplementedError

    def back(self):
        raise NotImplementedError

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.index = (self.index - 1) % self.count
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.index = (self.index + 1) % self.count
            elif event.key in CONFIRM_KEYS:
                self.confirm(self.index)
            elif pygame.K_1 <= event.key < pygame.K_1 + self.count:
                self.index = event.key - pygame.K_1
                self.confirm(self.index)
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.back()
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for i, r in enumerate(self.rects()):
                if r.collidepoint(event.pos):
                    self.index = i
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self.confirm(i)

    def update(self, dt):
        self.t += dt

    def draw_card(self, screen, rect, selected):
        lift = -8 if selected else 0
        rect = rect.move(0, lift)
        D.panel(screen, rect, radius=24, fill="white", alpha=235,
                outline="peach_dark" if selected else "ink_soft")
        if selected:
            D.draw_round_rect(screen, rect, D.PALETTE["peach_dark"], 24, width=4)
        return rect


class TitleScene:
    def __init__(self, app):
        self.app = app
        self.t = 0.0
        self.style_rect = pygame.Rect(W // 2 - 155, 390, 310, 42)

    def _toggle_style(self):
        self.app.medieval_mode = not self.app.medieval_mode
        D.set_style(self.app.medieval_mode)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self._toggle_style()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.style_rect.collidepoint(event.pos):
            self._toggle_style()
        elif (event.type == pygame.KEYDOWN and event.key in CONFIRM_KEYS) or \
                (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
            self.app.transition_to(TeamSelectScene(self.app))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        menu_background(screen, self.t)
        D.text(screen, config.TITLE, 72, "ink", (W // 2, 170), anchor="center")
        subtitle = "a medieval turn-based adventure" if self.app.medieval_mode else "a cozy turn-based adventure"
        subtitle_color = "cream" if self.app.medieval_mode else "ink_soft"
        D.text(screen, subtitle, 20, subtitle_color, (W // 2, 228), anchor="center",
               shadow=self.app.medieval_mode)
        for i, key in enumerate(["Warrior", "Paladin", "Mage", "Rogue"]):
            x = W // 2 - 150 + i * 100
            bob = math.sin(self.t * 3 + i) * 4
            if self.app.medieval_mode:
                draw_character(screen, "soldier", "idle", self.t + i * 0.12, x, 360 + bob, 62,
                               tint=D.PALETTE[CHARACTERS[key]["color"]])
            else:
                S.draw_body(screen, x, 360 + bob, 54, 60, CHARACTERS[key]["color"])
        D.panel(screen, self.style_rect, radius=12, fill="cream", alpha=242, outline="gold")
        style_label = "STYLE: MEDIEVAL   [M]" if self.app.medieval_mode else "STYLE: CLASSIC SLIME   [M]"
        D.text(screen, style_label, 15, "ink", self.style_rect.center, anchor="center", shadow=False)
        alpha = int(150 + 105 * (0.5 + 0.5 * math.sin(self.t * 3)))
        D.text(screen, "Press Enter to start", 22, "ink", (W // 2, 460), anchor="center", alpha=alpha)
        quit_color = "cream" if self.app.medieval_mode else "ink_soft"
        D.text(screen, "Esc to quit", 14, quit_color, (W // 2, 493), anchor="center",
               shadow=self.app.medieval_mode)


class TeamSelectScene(_CardMenu):
    CARD_W, CARD_H = 270, 330

    def __init__(self, app):
        super().__init__(app, len(PRESET_TEAMS))

    def rects(self):
        return card_row_rects(self.count, self.CARD_W, self.CARD_H, 150)

    def confirm(self, index):
        self.app.transition_to(LeaderSelectScene(self.app, PRESET_TEAMS[index]["members"]))

    def back(self):
        self.app.transition_to(TitleScene(self.app))

    def draw(self, screen):
        menu_background(screen, self.t)
        D.text(screen, "Choose your team", 36, "ink", (W // 2, 70), anchor="center")
        D.text(screen, "Left/Right to browse   Enter to pick   Esc to go back", 15, "ink_soft",
               (W // 2, 110), anchor="center", shadow=False)
        for i, (rect, team) in enumerate(zip(self.rects(), PRESET_TEAMS)):
            rect = self.draw_card(screen, rect, i == self.index)
            D.text(screen, team["name"], 22, "ink", (rect.centerx, rect.y + 30), anchor="center", shadow=False)
            for j, key in enumerate(team["members"]):
                c = CHARACTERS[key]
                y = rect.y + 70 + j * 84
                bob = math.sin(self.t * 3 + j + i) * 2 if i == self.index else 0
                if self.app.medieval_mode:
                    draw_character(screen, "soldier", "idle", self.t + i + j * 0.12,
                                   rect.x + 42, y + 50 + bob, 48,
                                   tint=D.PALETTE[c["color"]])
                else:
                    S.draw_body(screen, rect.x + 42, y + 50 + bob, 40, 44, c["color"])
                D.text(screen, c["name"], 17, "ink", (rect.x + 78, y + 8), shadow=False)
                D.text(screen, f"Skill: {c['skill']['name']}", 13, "ink_soft", (rect.x + 78, y + 32), shadow=False)
                D.text(screen, f"ATK {c['atk']}  SPD {c['spd']}", 13, "ink_soft", (rect.x + 78, y + 50), shadow=False)


class LeaderSelectScene(_CardMenu):
    CARD_W, CARD_H = 250, 330

    def __init__(self, app, members):
        super().__init__(app, len(members))
        self.members = members

    def rects(self):
        return card_row_rects(self.count, self.CARD_W, self.CARD_H, 160)

    def confirm(self, index):
        self.app.start_run(self.members, index)

    def back(self):
        self.app.transition_to(TeamSelectScene(self.app))

    def draw(self, screen):
        menu_background(screen, self.t)
        D.text(screen, "Choose your leader", 36, "ink", (W // 2, 70), anchor="center")
        D.text(screen, "Enemies only ever hit the leader. The leader's HP is the party's HP.", 15,
               "ink_soft", (W // 2, 110), anchor="center", shadow=False)
        D.text(screen, "Everyone still takes turns to attack, use skills or block.", 15,
               "ink_soft", (W // 2, 132), anchor="center", shadow=False)
        for i, (rect, key) in enumerate(zip(self.rects(), self.members)):
            c = CHARACTERS[key]
            rect = self.draw_card(screen, rect, i == self.index)
            bob = math.sin(self.t * 3) * 4 if i == self.index else 0
            if self.app.medieval_mode:
                draw_character(screen, "soldier", "idle", self.t, rect.centerx, rect.y + 120 + bob, 78,
                               tint=D.PALETTE[c["color"]])
            else:
                S.draw_body(screen, rect.centerx, rect.y + 120 + bob, 70, 78, c["color"])
            if i == self.index:
                D.draw_round_rect(screen, (rect.centerx - 9, rect.y + 24 + bob, 18, 10), D.PALETTE["gold"], 5)
            D.text(screen, c["name"], 22, "ink", (rect.centerx, rect.y + 150), anchor="center", shadow=False)
            D.text(screen, f"Leader HP {c['max_hp']}", 16, "pink_dark", (rect.centerx, rect.y + 184),
                   anchor="center", shadow=False)
            D.text(screen, f"ATK {c['atk']}   SPD {c['spd']}", 14, "ink_soft", (rect.centerx, rect.y + 212),
                   anchor="center", shadow=False)
            D.text(screen, c["skill"]["name"], 16, "ink", (rect.centerx, rect.y + 250), anchor="center", shadow=False)
            D.text(screen, c["skill"]["desc"], 13, "ink_soft", (rect.centerx, rect.y + 274), anchor="center",
                   shadow=False)
