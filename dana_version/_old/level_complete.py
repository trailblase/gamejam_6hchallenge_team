import pygame
import pixel_font as pf
import ui
from settings import WINDOW_WIDTH, WINDOW_HEIGHT, WHITE
from levels import LEVEL_COUNT


class LevelCompleteScene:
    def __init__(self, app):
        self.app = app
        self.data = app.data
        self.data.party.partial_heal(0.25)
        self.is_final = self.data.level_index >= LEVEL_COUNT - 1
        self.button = ui.Button((WINDOW_WIDTH / 2 - 110, WINDOW_HEIGHT / 2 + 60, 220, 50),
                                 "FINISH" if self.is_final else "NEXT LEVEL")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.rect.collidepoint(event.pos):
                self._advance()

    def _advance(self):
        if self.is_final:
            from victory import VictoryScene
            self.app.change_state(VictoryScene(self.app))
        else:
            from overworld import OverworldScene
            self.data.level_index += 1
            self.app.change_state(OverworldScene(self.app))

    def update(self, dt):
        self.button.update(pygame.mouse.get_pos())

    def draw(self, surface):
        surface.fill((20, 26, 22))
        pf.draw(surface, f"LEVEL {self.data.level_index + 1} CLEAR", 30, (170, 255, 190),
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2 - 60), center=True)
        pf.draw(surface, "The party rests, wounds partly mend...", 14, WHITE,
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2 - 10), center=True)
        ui.corruption_bar(surface, pygame.Rect(WINDOW_WIDTH / 2 - 150, WINDOW_HEIGHT / 2 + 20, 300, 16),
                           self.data.corruption.value)
        self.button.draw(surface)
