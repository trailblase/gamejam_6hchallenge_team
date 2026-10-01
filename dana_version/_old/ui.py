import pygame
import pixel_font as pf
from settings import PANEL_BG, PANEL_BORDER, PANEL_BORDER_LIT, HP_RED, HP_BG, WHITE, CORRUPTION_BAR, SHIELD_COLOR


def panel(surface, rect, lit=False):
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((*PANEL_BG, 230))
    surface.blit(s, rect.topleft)
    color = PANEL_BORDER_LIT if lit else PANEL_BORDER
    pygame.draw.rect(surface, color, rect, 3)


def shadow_ellipse(surface, center, w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 110), s.get_rect())
    surface.blit(s, (center[0] - w // 2, center[1] - h // 2))


def bar(surface, rect, frac, fg, bg=HP_BG, border=(0, 0, 0)):
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surface, bg, rect)
    fill = pygame.Rect(rect.x, rect.y, int(rect.width * frac), rect.height)
    pygame.draw.rect(surface, fg, fill)
    pygame.draw.rect(surface, border, rect, 2)


def hp_bar(surface, pos, width, height, hp, max_hp):
    rect = pygame.Rect(pos[0], pos[1], width, height)
    bar(surface, rect, hp / max_hp if max_hp else 0, HP_RED)


def corruption_bar(surface, rect, value):
    bar(surface, rect, value / 100.0, CORRUPTION_BAR, bg=(30, 10, 25))
    pf.draw(surface, f"CORRUPTION {int(value)}%", 14, WHITE, (rect.x, rect.y - 22))


def corruption_edge_meter(surface, screen_height, value, top=60, bottom_margin=20):
    """A vertical meter pinned to the left edge: corruption rises from the
    bottom like an encroaching tide."""
    width = 22
    height = screen_height - top - bottom_margin
    rect = pygame.Rect(8, top, width, height)
    pygame.draw.rect(surface, (30, 10, 25), rect)
    frac = max(0.0, min(1.0, value / 100.0))
    fill_h = int(height * frac)
    fill_rect = pygame.Rect(rect.x, rect.bottom - fill_h, width, fill_h)
    color = CORRUPTION_BAR if value < 85 else (230, 40, 60)
    pygame.draw.rect(surface, color, fill_rect)
    pygame.draw.rect(surface, (0, 0, 0), rect, 2)
    pf.draw(surface, "CORRUPTION", 11, WHITE, (rect.centerx, top - 14), center=True, shadow=False)
    pf.draw(surface, f"{int(value)}%", 12, WHITE, (rect.centerx, rect.bottom + 12), center=True, shadow=False)


def shield_bar(surface, pos, width, height, shield, max_hp):
    if shield <= 0 or max_hp <= 0:
        return
    rect = pygame.Rect(pos[0], pos[1], width, height)
    frac = max(0.0, min(1.0, shield / max_hp))
    pygame.draw.rect(surface, SHIELD_COLOR, (rect.x, rect.y, int(rect.width * frac), rect.height), 3)


class Button:
    def __init__(self, rect, label, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.enabled = enabled
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.enabled and self.rect.collidepoint(mouse_pos)

    def clicked(self, mouse_pos, mouse_down):
        return self.enabled and mouse_down and self.rect.collidepoint(mouse_pos)

    def draw(self, surface):
        lit = self.hovered
        color = PANEL_BORDER_LIT if lit else PANEL_BORDER
        bg = (50, 44, 66) if self.enabled else (30, 28, 36)
        pygame.draw.rect(surface, bg, self.rect)
        pygame.draw.rect(surface, color, self.rect, 3)
        txt_color = WHITE if self.enabled else (110, 108, 116)
        pf.draw(surface, self.label, 16, txt_color, self.rect.center, center=True, shadow=False)


STATUS_COLORS = {
    "slow": (90, 70, 170),
    "weak_jump": (170, 120, 50),
    "drain": (150, 20, 90),
}

STATUS_LABELS = {
    "slow": "SLOW",
    "weak_jump": "WEAK",
    "drain": "DRAIN",
}


def status_icons(surface, pos, statuses):
    x, y = pos
    for key, remaining in statuses.items():
        color = STATUS_COLORS.get(key, (120, 120, 120))
        rect = pygame.Rect(x, y, 26, 26)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (0, 0, 0), rect, 2)
        frac = max(0.0, min(1.0, remaining / 4.0))
        pygame.draw.rect(surface, (255, 255, 255), (x, y + 26, int(26 * frac), 4))
        x += 32
