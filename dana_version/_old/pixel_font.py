import pygame

_cache = {}
_fonts = {}


def _get_font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("segoeui,arial,sans-serif", size, bold=True)
    return _fonts[size]


def render(text, size, color):
    key = (text, size, color)
    if key in _cache:
        return _cache[key]
    font = _get_font(size)
    img = font.render(text, True, color)
    _cache[key] = img
    return img


def draw(surface, text, size, color, pos, center=False, shadow=True):
    img = render(text, size, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    if shadow:
        shadow_img = render(text, size, (0, 0, 0))
        surface.blit(shadow_img, (rect.x + 2, rect.y + 2))
    surface.blit(img, rect)
    return rect
