import pygame

from settings import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TITLE, BLACK
from game_data import GameData


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.data = GameData()

        from class_select import ClassSelectScene
        self.state = ClassSelectScene(self)

    def change_state(self, new_state):
        self.state = new_state

    def quit(self):
        self.running = False

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.state.handle_event(event)

            self.state.update(dt)

            self.screen.fill(BLACK)
            self.state.draw(self.screen)
            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    App().run()
