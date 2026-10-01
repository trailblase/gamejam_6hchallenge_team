import pygame
import pixel_font as pf
import ui
from settings import WINDOW_WIDTH, WINDOW_HEIGHT, WHITE


class VictoryScene:
    def __init__(self, app):
        self.app = app
        self.button = ui.Button((WINDOW_WIDTH / 2 - 120, WINDOW_HEIGHT / 2 + 70, 240, 50), "PLAY AGAIN")
        self.t = 0.0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.rect.collidepoint(event.pos):
                from class_select import ClassSelectScene
                self.app.change_state(ClassSelectScene(self.app))

    def update(self, dt):
        self.t += dt
        self.button.update(pygame.mouse.get_pos())

    def draw(self, surface):
        surface.fill((18, 24, 34))
        glow = int(20 + 10 * abs((self.t * 60) % 60 - 30))
        pf.draw(surface, "THE CORRUPTION IS CLEANSED", 28, (160, 230, 255),
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2 - 40), center=True)
        pf.draw(surface, "Your party stands victorious.", 16, WHITE,
                (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2 + 10), center=True)
        self.button.draw(surface)
