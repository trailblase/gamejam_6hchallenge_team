import pygame

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600
FPS = 60
TITLE = "Corruption"

TILE = 40

# ---- colors ----
WHITE = (240, 240, 245)
BLACK = (10, 10, 14)
PANEL_BG = (24, 22, 34)
PANEL_BORDER = (90, 80, 120)
PANEL_BORDER_LIT = (180, 140, 220)

SKY_TOP = (30, 20, 50)
SKY_BOTTOM = (70, 40, 80)

GROUND = (60, 50, 70)
GROUND_TOP = (90, 160, 110)
PLATFORM = (100, 90, 120)

CORRUPT_TILE = (120, 20, 90)
CORRUPT_TILE_PULSE = (200, 40, 140)

HAZARD_FIRE = (210, 90, 40)
HAZARD_ICE = (80, 160, 220)
HAZARD_VOID = (140, 40, 160)

PARTY_COLORS = {
    "Warrior": (210, 90, 70),
    "Paladin": (220, 200, 90),
    "Mage": (100, 130, 230),
    "Rogue": (90, 200, 130),
}

ENEMY_COLOR = (200, 60, 60)
ENEMY_BOSS_COLOR = (255, 120, 20)
OBSTACLE_COLOR = (70, 65, 85)

RESTORE_COLOR = (90, 220, 150)
PORTAL_COLOR_A = (120, 90, 230)
PORTAL_COLOR_B = (230, 120, 220)
PORTAL_LOCKED_COLOR = (70, 60, 90)
CAPTAIN_MARK = (255, 215, 90)
SHIELD_COLOR = (120, 210, 255)

HP_RED = (210, 50, 60)
HP_BG = (50, 20, 25)
XP_GOLD = (230, 190, 80)

CORRUPTION_BAR = (170, 30, 150)

GRID_COLS = 8
GRID_ROWS = 4
GRID_ORIGIN = (120, 160)
CELL = 86

CLASS_STATS = {
    "Warrior": dict(hp=46, atk=9, spd=5, rng=1, block=0.6, color=PARTY_COLORS["Warrior"]),
    "Paladin": dict(hp=52, atk=7, spd=4, rng=1, block=0.7, color=PARTY_COLORS["Paladin"]),
    "Mage":    dict(hp=26, atk=11, spd=6, rng=4, block=0.4, color=PARTY_COLORS["Mage"]),
    "Rogue":   dict(hp=32, atk=8, spd=9, rng=1, block=0.45, color=PARTY_COLORS["Rogue"]),
}

PRESET_TEAMS = [
    ["Warrior", "Mage", "Rogue"],
    ["Paladin", "Mage", "Rogue"],
    ["Warrior", "Paladin", "Mage"],
]

# Stat bonuses a class grants the captain while it rides along as a living
# follower (lost the instant that follower dies).
FOLLOWER_BUFFS = {
    "Warrior": {"hp": 14},
    "Paladin": {"block": 0.10},
    "Mage": {"atk": 4},
    "Rogue": {"spd": 3},
}

DOUBLE_JUMP_MULT = 0.82

def clamp(v, lo, hi):
    return max(lo, min(hi, v))
