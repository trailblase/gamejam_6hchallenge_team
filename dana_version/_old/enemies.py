import random

ENEMY_TYPES = {
    "Grunt":     dict(hp=18, atk=5, spd=3, rng=1, color=(200, 60, 60)),
    "Spitter":   dict(hp=14, atk=6, spd=4, rng=3, color=(160, 80, 200)),
    "Brute":     dict(hp=30, atk=7, spd=2, rng=1, color=(150, 40, 40)),
    "LevelBoss": dict(hp=42, atk=8, spd=4, rng=2, color=(220, 130, 40)),
    "Miniboss":  dict(hp=55, atk=9, spd=4, rng=2, color=(230, 100, 30)),
    "Boss":      dict(hp=90, atk=12, spd=5, rng=2, color=(255, 120, 20)),
}

NORMAL_POOL = ["Grunt", "Spitter", "Brute"]


class Enemy:
    def __init__(self, type_name, power_mult=1.0):
        stats = ENEMY_TYPES[type_name]
        self.type_name = type_name
        self.max_hp = round(stats["hp"] * power_mult)
        self.hp = self.max_hp
        self.base_atk = stats["atk"]
        self.spd = stats["spd"]
        self.rng = stats["rng"]
        self.color = stats["color"]
        self.power_mult = power_mult
        self.alive = True
        self.grid_pos = None

    @property
    def atk(self):
        return round(self.base_atk * self.power_mult)

    def buff(self, factor):
        self.power_mult += factor

    def take_damage(self, amount):
        amount = max(0, round(amount))
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.alive = False
        return amount


def build_encounter(kind, level_index, seed=None):
    """kind: 'normal' (single skippable foe), 'level_boss' (mandatory,
    guards a level's portal), 'miniboss' (level 3's mandatory boss),
    'final_boss' (level 5's mandatory, game-ending boss)."""
    rng = random.Random(seed) if seed is not None else random
    power = 1.0 + level_index * 0.1

    if kind == "final_boss":
        return [Enemy("Boss", 1.0 + level_index * 0.12)]
    if kind == "miniboss":
        return [Enemy("Miniboss", 1.0), Enemy("Grunt", 1.0)]
    if kind == "level_boss":
        return [Enemy("LevelBoss", power)]
    # normal
    return [Enemy(rng.choice(NORMAL_POOL), power)]
