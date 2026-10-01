"""Shared screen-space weather driven by the world corruption level."""

import math

import pygame

from data import config

_LAYER_CACHE = {}


def _layers(surface):
    size = surface.get_size()
    layers = _LAYER_CACHE.get(size)
    if layers is None:
        grayscale = pygame.Surface(size, depth=surface.get_bitsize())
        rain = pygame.Surface(size, pygame.SRCALPHA)
        vignette = pygame.Surface(size, pygame.SRCALPHA)
        layers = grayscale, rain, vignette
        _LAYER_CACHE[size] = layers
    return layers


def draw_corruption_weather(surface, corruption_fraction, elapsed):
    """Apply a restrained noir grade and stable light-to-heavy rain.

    Call after drawing the world/battlefield and before HUD elements so the
    weather affects the scene while keeping text and status panels crisp.
    """
    amount = max(0.0, min(1.0, corruption_fraction))
    if amount <= 0.001:
        return

    width, height = surface.get_size()
    grayscale, rain, vignette = _layers(surface)

    # Blend a true luminance-based grayscale copy with the original image.
    # Keeping the blend below half preserves a little color while reading as noir.
    pygame.transform.grayscale(surface, grayscale)
    grayscale.set_alpha(round(config.CORRUPTION_GRAYSCALE_MAX_ALPHA * amount))
    surface.blit(grayscale, (0, 0))

    # A soft edge darkening gives the scene a noir silhouette without dimming
    # the center or interfering with the UI.
    vignette.fill((0, 0, 0, 0))
    bands = 12
    band_width = max(3, min(width, height) // 30)
    for band in range(bands):
        inset = band * band_width
        rect = pygame.Rect(inset, inset, width - 2 * inset, height - 2 * inset)
        if rect.width <= 0 or rect.height <= 0:
            break
        alpha = round(config.CORRUPTION_VIGNETTE_MAX_ALPHA * amount * (1 - band / bands))
        pygame.draw.rect(vignette, (0, 0, 0, alpha), rect, width=band_width)
    surface.blit(vignette, (0, 0))

    # Distribute drops with deterministic per-drop speed and drift. Their paths
    # remain continuous from frame to frame, avoiding the old regimented jitter.
    intensity = math.sqrt(amount)
    drop_count = config.CORRUPTION_RAIN_BASE_DROPS + round(
        config.CORRUPTION_RAIN_MAX_EXTRA_DROPS * intensity
    )
    base_speed = config.CORRUPTION_RAIN_BASE_SPEED + config.CORRUPTION_RAIN_MAX_EXTRA_SPEED * intensity
    length = round(10 + 17 * intensity)
    alpha = round(105 + 140 * intensity)
    rain.fill((0, 0, 0, 0))
    for i in range(drop_count):
        seed = (i * 1_103_515_245 + 12_345) & 0x7FFFFFFF
        origin_x = seed % max(1, width)
        origin_y = (seed >> 9) % max(1, height)
        speed_factor = 0.72 + ((seed >> 17) & 0xFFFF) / 65535 * 0.56
        drift = 18 + ((seed >> 3) & 63)
        x = round((origin_x + elapsed * drift) % (width + 32)) - 16
        y = round((origin_y + elapsed * base_speed * speed_factor) % (height + length + 24)) - length
        slant = round(5 + 8 * intensity)
        pygame.draw.line(rain, (238, 244, 249, alpha), (x, y), (x - slant, y + length),
                         2 if intensity > 0.8 else 1)
    surface.blit(rain, (0, 0))
