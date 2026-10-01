"""Palette and drawing helpers. Every color in the game comes from PALETTE."""

import pygame

from data import config

PALETTE = {
    "cream": (250, 243, 228),
    "cream_dark": (232, 219, 198),
    "white": (255, 252, 246),
    "ink": (62, 50, 70),          # the one deep color, for text and outlines
    "ink_soft": (120, 104, 124),
    "sage": (168, 200, 160),
    "sage_light": (194, 220, 182),
    "sage_dark": (116, 158, 122),
    "grass": (184, 214, 166),
    "grass_dark": (170, 204, 154),
    "blue": (140, 176, 214),
    "blue_light": (186, 214, 236),
    "blue_dark": (108, 144, 188),
    "peach": (246, 198, 162),
    "peach_dark": (228, 156, 122),
    "pink": (234, 172, 184),
    "pink_dark": (204, 126, 146),
    "lavender": (196, 182, 224),
    "lavender_dark": (146, 124, 184),
    "gold": (240, 210, 132),
    "bark": (156, 122, 102),
    "plum": (150, 82, 204),       # corruption
    "plum_light": (206, 168, 240),
    "path": (232, 214, 176),
    "path_dark": (214, 192, 150),
}
_CLASSIC_PALETTE = PALETTE.copy()
_MEDIEVAL_PALETTE = {
    "cream": (227, 215, 188), "cream_dark": (183, 163, 130), "white": (239, 229, 201),
    "ink": (49, 41, 32), "ink_soft": (105, 86, 64),
    "sage": (136, 145, 83), "sage_light": (171, 171, 104), "sage_dark": (73, 91, 49),
    "grass": (114, 133, 56), "grass_dark": (94, 111, 48),
    "blue": (83, 127, 145), "blue_light": (145, 179, 182), "blue_dark": (53, 88, 103),
    "peach": (193, 149, 96), "peach_dark": (136, 91, 57),
    "pink": (181, 119, 108), "pink_dark": (128, 67, 61),
    "lavender": (142, 126, 151), "lavender_dark": (92, 73, 109),
    "gold": (200, 160, 78), "bark": (113, 77, 51),
    "plum": (105, 55, 112), "plum_light": (159, 111, 153),
    "path": (183, 165, 127), "path_dark": (132, 113, 81),
}
CURRENT_STYLE = "classic"
_CLASSIC_FONT_NAMES = "nunito,quicksand,varelaround,segoeui,trebuchetms,arial"
_MEDIEVAL_FONT_NAMES = "bookantiqua,georgia,garamond,timesnewroman,serif"
FONT_NAMES = _CLASSIC_FONT_NAMES


def set_style(medieval=False):
    """Switch shared interface colors and panel shapes for the active art mode."""
    global CURRENT_STYLE, FONT_NAMES
    style = "medieval" if medieval else "classic"
    if style == CURRENT_STYLE:
        return
    CURRENT_STYLE = style
    FONT_NAMES = _MEDIEVAL_FONT_NAMES if medieval else _CLASSIC_FONT_NAMES
    PALETTE.clear()
    PALETTE.update(_MEDIEVAL_PALETTE if medieval else _CLASSIC_PALETTE)
    _fonts.clear()
    _text_cache.clear()


def color(name):
    return PALETTE[name]


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def with_alpha(c, a):
    return (c[0], c[1], c[2], a)


# ------------------------------------------------------------------ shapes
def draw_round_rect(surface, rect, col, radius, width=0):
    """Rounded rectangle. A 4-tuple color draws translucently."""
    rect = pygame.Rect(rect)
    radius = int(max(0, min(radius, rect.width // 2, rect.height // 2)))
    if len(col) == 4 and col[3] < 255:
        tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tmp, col, tmp.get_rect(), width, border_radius=radius)
        surface.blit(tmp, rect.topleft)
    else:
        pygame.draw.rect(surface, col[:3], rect, width, border_radius=radius)


def soft_shadow(surface, rect, radius, alpha=60, offset=(0, 5)):
    rect = pygame.Rect(rect).move(offset)
    draw_round_rect(surface, rect, with_alpha(PALETTE["ink"], alpha), radius)


def oval_shadow(surface, cx, cy, w, h, alpha=70):
    w, h = max(2, int(w)), max(2, int(h))
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(tmp, with_alpha(PALETTE["ink"], alpha), tmp.get_rect())
    surface.blit(tmp, (cx - w // 2, cy - h // 2))


def panel(surface, rect, radius=16, fill="cream", alpha=225, outline="ink_soft"):
    rect = pygame.Rect(rect)
    if CURRENT_STYLE == "medieval":
        soft_shadow(surface, rect, 2, alpha=92, offset=(0, 4))
        cut = max(5, min(10, rect.height // 8, rect.width // 8))
        points = [(cut, 0), (rect.width - cut, 0), (rect.width, cut),
                  (rect.width, rect.height - cut), (rect.width - cut, rect.height),
                  (cut, rect.height), (0, rect.height - cut), (0, cut)]
        fill_col = PALETTE[fill] if isinstance(fill, str) else fill
        outline_col = PALETTE[outline] if isinstance(outline, str) else outline
        face = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(face, (*fill_col[:3], alpha), points)
        pygame.draw.polygon(face, (*outline_col[:3], 225), points, 2)
        if rect.width > 24 and rect.height > 12:
            pygame.draw.line(face, (*PALETTE["gold"], 115), (cut + 4, 4),
                             (rect.width - cut - 4, 4), 1)
        surface.blit(face, rect.topleft)
        return
    soft_shadow(surface, rect, radius)
    draw_round_rect(surface, rect, with_alpha(PALETTE[fill], alpha), radius)
    draw_round_rect(surface, rect, with_alpha(PALETTE[outline], 140), radius, width=2)


# -------------------------------------------------------------------- text
_fonts = {}
_text_cache = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(FONT_NAMES, size, bold=True)
    return _fonts[size]


def render_text(txt, size, col):
    key = (txt, size, col)
    img = _text_cache.get(key)
    if img is None:
        img = font(size).render(txt, True, col)
        if len(_text_cache) > 800:
            _text_cache.clear()
        _text_cache[key] = img
    return img


def text(surface, txt, size, col="ink", pos=(0, 0), anchor="topleft", shadow=True, alpha=255):
    c = PALETTE[col] if isinstance(col, str) else col
    img = render_text(txt, size, c)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        sh = render_text(txt, size, PALETTE["ink"] if c != PALETTE["ink"] else PALETTE["cream"])
        sh = sh.copy()
        sh.set_alpha(int(70 * alpha / 255))
        surface.blit(sh, rect.move(1, 2))
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    surface.blit(img, rect)
    return rect


# -------------------------------------------------------------------- bars
class AnimatedBar:
    """Fill eases toward the real value; a lighter chunk trails behind on
    damage so hits read clearly."""

    def __init__(self, value, maximum):
        self.value = value
        self.maximum = maximum
        self.shown = value
        self.chunk = value
        self.chunk_wait = 0.0

    def set(self, value, maximum=None):
        if maximum is not None:
            self.maximum = maximum
        if value < self.value:
            self.chunk = max(self.chunk, self.shown)
            self.chunk_wait = config.BAR_CHUNK_DELAY
        self.value = value

    def update(self, dt):
        self.shown += (self.value - self.shown) * min(1.0, config.BAR_LERP * dt)
        if abs(self.value - self.shown) < 0.05:
            self.shown = self.value
        if self.chunk_wait > 0:
            self.chunk_wait -= dt
        else:
            self.chunk += (self.shown - self.chunk) * min(1.0, config.BAR_CHUNK_LERP * dt)
        if self.chunk < self.shown:
            self.chunk = self.shown

    def draw(self, surface, rect, fill="pink_dark", chunk="cream", back="cream_dark"):
        rect = pygame.Rect(rect)
        r = rect.height // 2
        draw_round_rect(surface, rect.inflate(4, 4), PALETTE["ink_soft"], r + 2)
        draw_round_rect(surface, rect, PALETTE[back], r)
        mx = max(1, self.maximum)
        cw = int(rect.width * max(0.0, min(1.0, self.chunk / mx)))
        sw = int(rect.width * max(0.0, min(1.0, self.shown / mx)))
        if cw > 0:
            draw_round_rect(surface, (rect.x, rect.y, max(cw, rect.height), rect.height), PALETTE[chunk], r)
        if sw > 0:
            draw_round_rect(surface, (rect.x, rect.y, max(sw, rect.height), rect.height), PALETTE[fill], r)
            hl = pygame.Rect(rect.x + 3, rect.y + 2, max(0, max(sw, rect.height) - 6), max(1, rect.height // 3))
            draw_round_rect(surface, hl, with_alpha(PALETTE["white"], 90), hl.height // 2)


# -------------------------------------------------------------- easing
def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)
