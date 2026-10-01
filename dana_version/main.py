"""Entry point: window, fixed 60 FPS loop, scene manager, debug overlay."""

import random

import pygame

from data import config
from ui import audio
from ui import draw as D


class App:
    def __init__(self, seed=None):
        pygame.init()
        audio.init()
        self.screen = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H))
        pygame.display.set_caption(config.TITLE)
        self.clock = pygame.time.Clock()
        if seed is None:
            seed = config.SEED if config.SEED is not None else random.randrange(1_000_000)
        self.seed = seed
        self.rng = random.Random(seed)
        print(f"[app] RNG seed {seed}  (set data/config.py SEED to replay)")
        self.run = None
        self.first_run = True
        self.debug = False
        self.running = True
        self.frame_ms = 0.0

        from scenes.menus import TitleScene
        self.state = TitleScene(self)

    def change_state(self, scene):
        self.state = scene

    def transition_to(self, scene):
        from scenes.transition import IrisTransition
        self.state = IrisTransition(self, self.screen.copy(), scene)

    def start_run(self, team, leader_index):
        from game_state import RunState
        from overworld.scene import OverworldScene
        self.run = RunState(team, leader_index, self.rng)
        print(f"[app] new run: team {team}, leader {team[leader_index]}")
        self.transition_to(OverworldScene(self))

    def quit(self):
        self.running = False

    def tick(self, dt, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                self.debug = not self.debug
            else:
                self.state.handle_event(event)
        self.state.update(dt)
        self.state.draw(self.screen)
        if self.debug:
            self._draw_debug()

    def main_loop(self):
        while self.running:
            ms = self.clock.tick(config.FPS)
            self.frame_ms = ms
            self.tick(min(ms / 1000, config.MAX_DT), pygame.event.get())
            pygame.display.flip()
        pygame.quit()

    def _draw_debug(self):
        lines = [f"scene {type(self.state).__name__}   seed {self.seed}   frame {self.frame_ms:.0f} ms "
                 f"({self.clock.get_fps():.0f} fps)"]
        if hasattr(self.state, "debug_lines"):
            lines += self.state.debug_lines()
        lines.append("F1 debug   F2 instant win   F3 teleport to next boss   F4 force corruption spread")
        height = 10 + 18 * len(lines)
        box = pygame.Rect(8, config.WINDOW_H - height - 8, config.WINDOW_W - 16, height)
        D.draw_round_rect(self.screen, box, D.with_alpha(D.PALETTE["ink"], 200), 10)
        for i, line in enumerate(lines):
            D.text(self.screen, line, 13, "cream", (box.x + 10, box.y + 6 + i * 18), shadow=False)


if __name__ == "__main__":
    App().main_loop()
