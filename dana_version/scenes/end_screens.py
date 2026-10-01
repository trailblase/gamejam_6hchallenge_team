"""Game over (with Retry) and the win screen."""

import math

import pygame

from data import config
from data.characters import CHARACTERS
from scenes.menus import menu_background, CONFIRM_KEYS
from ui import draw as D
from ui import sprites as S

W, H = config.WINDOW_W, config.WINDOW_H


class GameOverScene:
    def __init__(self, app, overworld):
        self.app = app
        self.overworld = overworld
        self.t = 0.0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in CONFIRM_KEYS:
            self.overworld.retry()
            self.app.transition_to(self.overworld)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from scenes.menus import TitleScene
            self.app.transition_to(TitleScene(self.app))

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        menu_background(screen, self.t)
        D.text(screen, "Defeated", 64, "pink_dark", (W // 2, 180), anchor="center")
        S.draw_body(screen, W // 2, 330, 80, 60, CHARACTERS[self.app.run.leader_key]["color"], squash=0.6)
        run = self.app.run
        D.text(screen, f"Bosses defeated: {len(run.bosses_defeated)}/{config.BOSSES_TO_WIN}", 18, "ink",
               (W // 2, 380), anchor="center", shadow=False)
        D.text(screen, "Defeated foes stay defeated. Your rewards are kept.", 15, "ink_soft",
               (W // 2, 410), anchor="center", shadow=False)
        alpha = int(150 + 105 * (0.5 + 0.5 * math.sin(self.t * 3)))
        D.text(screen, "Enter: Retry      Esc: Title", 22, "ink", (W // 2, 470), anchor="center", alpha=alpha)


class WinScene:
    def __init__(self, app):
        self.app = app
        self.t = 0.0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and (event.key in CONFIRM_KEYS or event.key == pygame.K_ESCAPE):
            from scenes.menus import TitleScene
            self.app.transition_to(TitleScene(self.app))

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        menu_background(screen, self.t)
        D.text(screen, "The land is cleansed!", 52, "sage_dark", (W // 2, 160), anchor="center")
        run = self.app.run
        for i, key in enumerate(run.team):
            hop = abs(math.sin(self.t * 4 + i)) * 14
            S.draw_body(screen, W // 2 - 110 + i * 110, 330 - hop, 62, 68, CHARACTERS[key]["color"])
        D.text(screen, f"Battles fought: {run.battles_fought}", 18, "ink", (W // 2, 390), anchor="center",
               shadow=False)
        alpha = int(150 + 105 * (0.5 + 0.5 * math.sin(self.t * 3)))
        D.text(screen, "Press Enter to return to the title", 20, "ink", (W // 2, 460), anchor="center",
               alpha=alpha)
