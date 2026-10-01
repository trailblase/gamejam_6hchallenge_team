"""Procedural rounded characters, trees and props. No image files."""

import math

import pygame

from ui.draw import PALETTE, mix, oval_shadow, draw_round_rect


def draw_body(surface, cx, feet_y, w, h, col_name, facing_x=0.0, squash=0.0, flash=0.0,
              alpha=255, scale=1.0, shadow=True, blush=True):
    """A soft blob creature: rounded body, two eyes, blush. `squash` > 0
    widens and flattens (hit reaction); `flash` 0..1 tints toward white."""
    w = w * scale * (1 + 0.22 * squash)
    h = h * scale * (1 - 0.18 * squash)
    if w < 2 or h < 2:
        return
    if shadow:
        oval_shadow(surface, cx, feet_y, w * 0.95, max(6, w * 0.28), alpha=int(70 * alpha / 255))

    base = PALETTE[col_name] if isinstance(col_name, str) else col_name
    body_col = mix(base, PALETTE["white"], flash)
    outline = mix(base, PALETTE["ink"], 0.35)

    pad = 4
    surf = pygame.Surface((int(w) + pad * 2, int(h) + pad * 2), pygame.SRCALPHA)
    body = pygame.Rect(pad, pad, int(w), int(h))
    radius = int(min(w, h) * 0.45)
    pygame.draw.rect(surf, outline, body.inflate(4, 4), border_radius=radius + 2)
    pygame.draw.rect(surf, body_col, body, border_radius=radius)
    shine = pygame.Rect(body.x + w * 0.18, body.y + h * 0.12, w * 0.3, h * 0.16)
    pygame.draw.ellipse(surf, (*mix(body_col, PALETTE["white"], 0.55), 160), shine)

    eye_y = body.y + h * 0.42
    eye_dx = w * 0.18
    look = facing_x * w * 0.08
    eye_w, eye_h = max(3, w * 0.09), max(4, h * 0.14)
    for side in (-1, 1):
        ex = body.centerx + side * eye_dx + look
        pygame.draw.ellipse(surf, PALETTE["ink"], (ex - eye_w / 2, eye_y - eye_h / 2, eye_w, eye_h))
        pygame.draw.circle(surf, PALETTE["white"], (int(ex + eye_w * 0.15), int(eye_y - eye_h * 0.2)),
                           max(1, int(eye_w * 0.25)))
        if blush:
            bx = body.centerx + side * w * 0.3 + look
            pygame.draw.ellipse(surf, (*PALETTE["pink"], 150),
                                (bx - w * 0.08, eye_y + h * 0.1, w * 0.16, h * 0.08))
    if alpha < 255:
        surf.set_alpha(alpha)
    surface.blit(surf, (cx - surf.get_width() / 2, feet_y - surf.get_height() + pad))


def draw_tree(surface, x, y, tile, t=0.0):
    """Tree whose trunk base sits at (x, y) = bottom-center of its tile."""
    oval_shadow(surface, x, y - 2, tile * 0.9, tile * 0.32, alpha=60)
    trunk = pygame.Rect(0, 0, tile * 0.24, tile * 0.5)
    trunk.midbottom = (x, y - 2)
    draw_round_rect(surface, trunk, PALETTE["bark"], 5)
    sway = math.sin(t * 0.8 + x * 0.05) * 1.2
    cy = y - tile * 0.95
    r = tile * 0.52
    pygame.draw.circle(surface, mix(PALETTE["sage_dark"], PALETTE["ink"], 0.15), (x + sway, cy + 4), r + 2)
    pygame.draw.circle(surface, PALETTE["sage_dark"], (x - r * 0.45 + sway, cy + r * 0.2), r * 0.72)
    pygame.draw.circle(surface, PALETTE["sage_dark"], (x + r * 0.45 + sway, cy + r * 0.2), r * 0.72)
    pygame.draw.circle(surface, PALETTE["sage"], (x + sway, cy - r * 0.15), r * 0.8)
    pygame.draw.circle(surface, PALETTE["sage_light"], (x - r * 0.25 + sway, cy - r * 0.4), r * 0.32)


def draw_bush(surface, x, y, tile):
    oval_shadow(surface, x, y - 3, tile * 0.85, tile * 0.28, alpha=55)
    r = tile * 0.3
    base_y = y - r - 2
    pygame.draw.circle(surface, PALETTE["sage_dark"], (x - r * 0.7, base_y + 2), r)
    pygame.draw.circle(surface, PALETTE["sage_dark"], (x + r * 0.7, base_y + 2), r)
    pygame.draw.circle(surface, PALETTE["sage"], (x, base_y - r * 0.3), r * 1.05)
    pygame.draw.circle(surface, PALETTE["pink"], (x + r * 0.4, base_y - r * 0.6), 3)
    pygame.draw.circle(surface, PALETTE["cream"], (x - r * 0.5, base_y - r * 0.1), 2)


def draw_spring(surface, x, y, used, t):
    oval_shadow(surface, x, y + 2, 46, 14, alpha=55)
    rim = pygame.Rect(0, 0, 44, 22)
    rim.center = (x, y - 6)
    pygame.draw.ellipse(surface, PALETTE["cream_dark"], rim)
    pygame.draw.ellipse(surface, mix(PALETTE["cream_dark"], PALETTE["ink"], 0.25), rim, 2)
    pool = rim.inflate(-12, -8)
    if used:
        pygame.draw.ellipse(surface, PALETTE["path_dark"], pool)
        pygame.draw.circle(surface, PALETTE["bark"], (pool.centerx - 5, pool.centery), 2)
        pygame.draw.circle(surface, PALETTE["bark"], (pool.centerx + 6, pool.centery + 1), 2)
    else:
        pygame.draw.ellipse(surface, PALETTE["blue"], pool)
        glint = 0.5 + 0.5 * math.sin(t * 3)
        pygame.draw.ellipse(surface, mix(PALETTE["blue_light"], PALETTE["white"], glint),
                            pool.inflate(-pool.width * 0.5, -pool.height * 0.4))
        for i in range(3):
            phase = (t * 0.7 + i / 3) % 1.0
            sy = y - 12 - phase * 26
            sx = x + math.sin(phase * 6 + i * 2) * 8
            pygame.draw.circle(surface, PALETTE["blue_light"], (sx, sy), max(1, int(3 * (1 - phase))))


def draw_glow(surface, cx, cy, radius, col_name, strength=1.0):
    r = int(radius)
    if r < 2:
        return
    tmp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    base = PALETTE[col_name]
    for i in range(6, 0, -1):
        rr = int(r * i / 6)
        a = int(28 * strength * (7 - i) / 6)
        pygame.draw.circle(tmp, (*base, a), (r, r), rr)
    surface.blit(tmp, (cx - r, cy - r))


def draw_chest(surface, x, y, opened, t):
    """Chest whose bottom-center sits at (x, y)."""
    oval_shadow(surface, x, y, 40, 12, alpha=60)
    body = pygame.Rect(0, 0, 34, 22)
    body.midbottom = (x, y - 2)
    outline = mix(PALETTE["bark"], PALETTE["ink"], 0.35)
    draw_round_rect(surface, body.inflate(4, 4), outline, 9)
    draw_round_rect(surface, body, PALETTE["peach_dark"], 7)
    pygame.draw.rect(surface, PALETTE["bark"], (body.x, body.y + 8, body.width, 5))
    if opened:
        lid = pygame.Rect(0, 0, 34, 10)
        lid.midbottom = (x, body.y - 4)
        draw_round_rect(surface, lid.inflate(4, 4), outline, 6)
        draw_round_rect(surface, lid, PALETTE["peach"], 5)
        inner = pygame.Rect(body.x + 4, body.y + 2, body.width - 8, 6)
        draw_round_rect(surface, inner, mix(PALETTE["bark"], PALETTE["ink"], 0.5), 3)
    else:
        lid = pygame.Rect(0, 0, 36, 12)
        lid.midbottom = (x, body.y + 3)
        draw_round_rect(surface, lid.inflate(4, 4), outline, 7)
        draw_round_rect(surface, lid, PALETTE["peach"], 6)
        glint = 0.5 + 0.5 * math.sin(t * 3 + x)
        latch = pygame.Rect(0, 0, 8, 9)
        latch.center = (x, body.y + 6)
        draw_round_rect(surface, latch, mix(PALETTE["gold"], PALETTE["white"], glint * 0.6), 3)


def draw_guide(surface, cx, feet_y, t, facing_x=0.0):
    """Friendly slime with a mustache. Feet sit at (cx, feet_y)."""
    bob = math.sin(t * 2.2) * 2
    w, h = 44, 36
    draw_body(surface, cx, feet_y - bob, w, h, "sage", facing_x=facing_x)
    my = feet_y - bob - h * 0.40
    col = PALETTE["ink"]
    pygame.draw.ellipse(surface, col, (cx - 13, my, 11, 5))
    pygame.draw.ellipse(surface, col, (cx + 2, my, 11, 5))
    pygame.draw.circle(surface, col, (int(cx - 13), int(my + 4)), 2)
    pygame.draw.circle(surface, col, (int(cx + 13), int(my + 4)), 2)
