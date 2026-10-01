import pygame
import pixel_font as pf
import ui
from settings import WINDOW_WIDTH, WINDOW_HEIGHT, WHITE


class GameOverScene:
    def __init__(self, app):
        self.app = app
        self.button = ui.Button((WINDOW_WIDTH / 2 - 120, WINDOW_HEIGHT / 2 + 60, 240, 50), "TRY AGAIN")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.rect.collidepoint(event.pos):
                from class_select import ClassSelectScene
                self.app.change_state(ClassSelectScene(self.app))

    def update(self, dt):
        self.button.update(pygame.mouse.get_pos())

    def draw(self, surface):
        surface.fill((28, 14, 18))
        pf.draw(surface, "THE CORRUPTION CONSUMES YOU", 26, (255, 90, 90),
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2 - 40), center=True)
        pf.draw(surface, "Your party has fallen.", 15, WHITE,
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2), center=True)
        self.button.draw(surface)
