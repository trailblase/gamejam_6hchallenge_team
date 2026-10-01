"""Circular iris wipe: closes on a snapshot of the old scene, opens on the new one."""

import math

import pygame

from data import config
from ui import draw as D


class IrisTransition:
    def __init__(self, app, snapshot, target):
        self.app = app
        self.snapshot = snapshot
        self.target = target
        self.t = 0.0
        self.half = config.IRIS_SECONDS / 2
        w, h = snapshot.get_size()
        self.center = (w // 2, h // 2)
        self.max_r = math.hypot(w, h) / 2 + 4
        self.mask = pygame.Surface((w, h), pygame.SRCALPHA)

    def handle_event(self, event):
        pass

    def update(self, dt):
        self.t += dt
        if self.t >= self.half * 2:
            self.app.change_state(self.target)

    def draw(self, screen):
        if self.t < self.half:
            screen.blit(self.snapshot, (0, 0))
            r = self.max_r * (1 - D.ease_in_out(self.t / self.half))
        else:
            self.target.draw(screen)
            r = self.max_r * D.ease_in_out((self.t - self.half) / self.half)
        self.mask.fill(D.with_alpha(D.PALETTE["ink"], 255))
        if r > 1:
            pygame.draw.circle(self.mask, (0, 0, 0, 0), self.center, int(r))
        screen.blit(self.mask, (0, 0))

    def debug_lines(self):
        return [f"transition -> {type(self.target).__name__} ({self.t:.2f}s)"]
