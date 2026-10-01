"""Loader and renderer for the bundled Tiny RPG soldier/orc animations."""

from functools import lru_cache
from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "medieval"
FRAME_SIZE = 100
ANIMATIONS = ("idle", "walk", "attack01", "attack02", "attack03", "hurt", "death")
FRAME_RATES = {"idle": 7.0, "walk": 10.0, "attack01": 12.0, "attack02": 12.0,
               "attack03": 12.0, "hurt": 10.0, "death": 7.0}
_SHEETS = {}


def _load_actor(actor):
    if actor in _SHEETS:
        return _SHEETS[actor]

    sheets = {}
    idle_bounds = []
    for animation in ANIMATIONS:
        path = ASSET_DIR / f"{actor}_{animation}.png"
        if not path.exists():
            continue
        image = pygame.image.load(str(path)).convert_alpha()
        frames = []
        for x in range(0, image.get_width(), FRAME_SIZE):
            cell_rect = pygame.Rect(x, 0, FRAME_SIZE, FRAME_SIZE)
            cell = image.subsurface(cell_rect).copy()
            bounds = cell.get_bounding_rect(min_alpha=1)
            if not bounds.width or not bounds.height:
                continue
            frames.append((cell.subsurface(bounds).copy(), bounds))
            if animation in ("idle", "walk"):
                idle_bounds.append(bounds)
        if frames:
            sheets[animation] = frames

    if not idle_bounds:
        raise FileNotFoundError(f"No idle animation found for {actor} in {ASSET_DIR}")

    # The common anchor and body height keep feet planted and character scale
    # stable while animation frames extend an arm or weapon in either direction.
    body = idle_bounds[0].copy()
    for rect in idle_bounds[1:]:
        body.union_ip(rect)
    result = (sheets, body)
    _SHEETS[actor] = result
    return result


@lru_cache(maxsize=768)
def _scaled_frame(actor, animation, frame_index, target_height, tint):
    sheets, body = _load_actor(actor)
    frames = sheets.get(animation) or sheets["idle"]
    source, bounds = frames[frame_index % len(frames)]
    scale = max(0.1, target_height / body.height)
    size = (max(1, round(source.get_width() * scale)), max(1, round(source.get_height() * scale)))
    scaled = pygame.transform.scale(source, size)
    if tint is not None:
        multipliers = tuple(round(140 + channel * 0.45) for channel in tint)
        scaled.fill((*multipliers, 255), special_flags=pygame.BLEND_RGBA_MULT)
    # Return scaled art and its offset from the stable actor center/feet anchor.
    offset = (round((bounds.centerx - body.centerx) * scale),
              round((bounds.bottom - body.bottom) * scale))
    return scaled, offset


def draw_character(surface, actor, animation, elapsed, center_x, feet_y, target_height,
                   *, flip=False, alpha=255, tint=None):
    """Draw a nearest-neighbor animated actor aligned to a stable feet anchor."""
    sheets, _ = _load_actor(actor)
    frames = sheets.get(animation) or sheets["idle"]
    rate = FRAME_RATES.get(animation, 8.0)
    frame_index = int(max(0.0, elapsed) * rate)
    if animation in ("idle", "walk"):
        frame_index %= len(frames)
    else:
        frame_index = min(frame_index, len(frames) - 1)
    tint_rgb = tuple(tint[:3]) if tint is not None else None
    frame, offset = _scaled_frame(actor, animation, frame_index, int(target_height), tint_rgb)
    if flip:
        frame = pygame.transform.flip(frame, True, False)
        offset = (-offset[0], offset[1])
    if alpha < 255:
        frame = frame.copy()
        frame.set_alpha(max(0, min(255, alpha)))
    dest = (round(center_x + offset[0] - frame.get_width() / 2),
            round(feet_y + offset[1] - frame.get_height()))
    surface.blit(frame, dest)
