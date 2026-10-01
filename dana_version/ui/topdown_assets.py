"""Crops and small drawing helpers for the top-down medieval texture pack."""

from functools import lru_cache
import math
from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "top_down"
_ATLAS = {}


def _image(name):
    image = _ATLAS.get(name)
    if image is None:
        image = pygame.image.load(str(ASSET_DIR / name)).convert_alpha()
        _ATLAS[name] = image
    return image


@lru_cache(maxsize=96)
def _crop(name, rect):
    left, top, right, bottom = rect
    crop_rect = pygame.Rect(left, top, right - left, bottom - top)
    return _image(name).subsurface(crop_rect).copy()


def ground_tile(kind, tx, ty):
    if kind == "path":
        # A repeatable cobble tile keeps the atlas's autotile edges aligned.
        return _crop("TX Tileset Grass.png", (0, 128, 32, 160))
    if kind == "water":
        return _water_tile((tx + ty) % 4)
    # The top three rows are seamless grass variations, including small weeds.
    index = (tx * 13 + ty * 7 + (tx * ty) % 5) % 24
    x = (index % 8) * 32
    y = (index // 8) * 32
    return _crop("TX Tileset Grass.png", (x, y, x + 32, y + 32))


@lru_cache(maxsize=4)
def _water_tile(variant):
    tile = pygame.Surface((32, 32))
    tile.fill((55, 94, 103))
    # A restrained rippled pond texture that fits the pack's subdued palette.
    for row in range(4):
        y = 4 + row * 8
        x = (variant * 5 + row * 9) % 19
        pygame.draw.line(tile, (76, 118, 124), (x, y), (x + 7, y), 1)
        pygame.draw.line(tile, (44, 77, 88), (x + 3, y + 2), (x + 10, y + 2), 1)
    return tile


@lru_cache(maxsize=24)
def scaled_prop(name, size):
    rects = {
        "tree_a": ("TX Plant.png", (24, 14, 137, 153)),
        "tree_b": ("TX Plant.png", (161, 17, 257, 153)),
        "tree_c": ("TX Plant.png", (295, 31, 374, 151)),
        "bush_a": ("TX Plant.png", (38, 198, 60, 217)),
        "bush_b": ("TX Plant.png", (98, 195, 125, 220)),
        "bush_c": ("TX Plant.png", (156, 190, 194, 222)),
        "bush_d": ("TX Plant.png", (216, 185, 263, 227)),
        "bush_e": ("TX Plant.png", (282, 186, 321, 231)),
        "bush_f": ("TX Plant.png", (346, 190, 386, 225)),
        "chest": ("TX Props.png", (96, 30, 128, 64)),
        "spring": ("TX Props.png", (353, 269, 447, 341)),
    }
    atlas, rect = rects[name]
    source = _crop(atlas, rect)
    return pygame.transform.scale(source, size)


@lru_cache(maxsize=1)
def battle_floor_tile():
    return _crop("TX Tileset Stone Ground.png", (96, 96, 128, 128))


@lru_cache(maxsize=3)
def _tree_shadow(width):
    shadow = pygame.Surface((width, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (37, 43, 27, 105), shadow.get_rect())
    return shadow


def draw_tree(surface, x, feet_y, variant=0):
    sizes = ((113, 139), (96, 136), (79, 120))
    w, h = sizes[variant % len(sizes)]
    shadow = _tree_shadow(round(w * 0.74))
    surface.blit(shadow, (round(x - shadow.get_width() / 2), round(feet_y - 12)))
    sprite = scaled_prop(f"tree_{'abc'[variant % 3]}", (w, h))
    surface.blit(sprite, (round(x - w / 2), round(feet_y - h)))


def draw_bush(surface, x, feet_y, variant=0):
    name = f"bush_{'abcdef'[variant % 6]}"
    size = (38 + (variant % 3) * 4, 30 + (variant % 2) * 5)
    sprite = scaled_prop(name, size)
    surface.blit(sprite, (round(x - size[0] / 2), round(feet_y - size[1])))


def draw_chest(surface, x, feet_y, opened=False):
    sprite = scaled_prop("chest", (38, 40))
    surface.blit(sprite, (round(x - 19), round(feet_y - 38)))
    if opened:
        pygame.draw.rect(surface, (47, 34, 24), (round(x - 9), round(feet_y - 30), 18, 7))
        pygame.draw.line(surface, (177, 139, 78), (x - 8, feet_y - 19), (x + 8, feet_y - 19), 2)


def draw_spring(surface, x, feet_y, used=False):
    sprite = scaled_prop("spring", (76, 58))
    surface.blit(sprite, (round(x - 38), round(feet_y - 48)))
    if used:
        veil = pygame.Surface((26, 14), pygame.SRCALPHA)
        veil.fill((39, 49, 50, 150))
        surface.blit(veil, (round(x - 13), round(feet_y - 29)))


@lru_cache(maxsize=48)
def _player_frame(direction, height, tint):
    boxes = ((6, 14, 27, 58), (38, 10, 59, 58), (69, 13, 90, 58))
    frame = _crop("TX Player.png", boxes[direction])
    size = (max(1, round(frame.get_width() * height / frame.get_height())), height)
    frame = pygame.transform.scale(frame, size)
    if tint is not None:
        multipliers = tuple(round(140 + channel * 0.45) for channel in tint)
        frame.fill((*multipliers, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return frame


@lru_cache(maxsize=1)
def _player_shadow():
    shadow = pygame.transform.scale(_crop("TX Player.png", (99, 32, 126, 60)), (27, 16))
    shadow.set_alpha(118)
    return shadow


def draw_player(surface, x, feet_y, facing, tint, elapsed, moving=False):
    """Draw the atlas's front, back, or side-facing overworld adventurer."""
    fx, fy = facing
    if abs(fx) > abs(fy):
        direction = 2
    else:
        direction = 1 if fy < 0 else 0
    sprite = _player_frame(direction, 34, tuple(tint[:3]))
    if direction == 2 and fx < 0:
        sprite = pygame.transform.flip(sprite, True, False)
    bob = round(math.sin(elapsed * 12) * 1.5) if moving else 0
    shadow = _player_shadow()
    surface.blit(shadow, (round(x - shadow.get_width() / 2), round(feet_y - 13)))
    surface.blit(sprite, (round(x - sprite.get_width() / 2), round(feet_y - sprite.get_height() + bob)))


@lru_cache(maxsize=4)
def _menu_backdrop(size):
    width, height = size
    backdrop = pygame.Surface(size)
    for y in range(0, height, 32):
        for x in range(0, width, 32):
            backdrop.blit(ground_tile("grass", x // 32, y // 32), (x, y))
    shade = pygame.Surface(size, pygame.SRCALPHA)
    shade.fill((22, 25, 24, 88))
    backdrop.blit(shade, (0, 0))
    draw_tree(backdrop, 88, height + 16, 0)
    draw_tree(backdrop, width - 92, height + 16, 1)
    return backdrop


def draw_menu_backdrop(surface, t):
    surface.blit(_menu_backdrop(surface.get_size()), (0, 0))

