from settings import CLASS_STATS, FOLLOWER_BUFFS


class Character:
    def __init__(self, class_name, name=None):
        stats = CLASS_STATS[class_name]
        self.class_name = class_name
        self.name = name or class_name
        self.max_hp = stats["hp"]
        self.hp = stats["hp"]
        self.base_atk = stats["atk"]
        self.base_spd = stats["spd"]
        self.rng = stats["rng"]
        self.block_pct = stats["block"]
        self.color = stats["color"]

        self.equipment = {"weapon": None, "armor": None, "accessory": None}

        self.blocking = False
        self.alive = True
        self.grid_pos = None
        self.shield = 0

        self.is_captain = False
        self.party = None  # back-reference, set by Party

    def _support_bonuses(self):
        """Buffs the two living followers grant the captain. Followers
        never act in battle - this is the only thing they contribute."""
        if not self.is_captain or self.party is None:
            return []
        return [
            FOLLOWER_BUFFS.get(m.class_name, {})
            for m in self.party.members
            if m is not self and m.alive
        ]

    @property
    def atk(self):
        bonus = sum(item.atk for item in self.equipment.values() if item)
        bonus += sum(b.get("atk", 0) for b in self._support_bonuses())
        return self.base_atk + bonus

    @property
    def spd(self):
        bonus = sum(item.spd for item in self.equipment.values() if item)
        bonus += sum(b.get("spd", 0) for b in self._support_bonuses())
        return self.base_spd + bonus

    @property
    def max_hp_total(self):
        bonus = sum(item.hp for item in self.equipment.values() if item)
        bonus += sum(b.get("hp", 0) for b in self._support_bonuses())
        return self.max_hp + bonus

    @property
    def block_total(self):
        bonus = sum(item.block for item in self.equipment.values() if item)
        bonus += sum(b.get("block", 0) for b in self._support_bonuses())
        return min(0.9, self.block_pct + bonus)

    def take_damage(self, amount):
        if self.blocking:
            amount *= (1 - self.block_total)
        amount = max(0, round(amount))
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.alive = False
        return amount

    def heal(self, amount):
        self.hp = min(self.max_hp_total, self.hp + amount)

    def ready_for_battle(self):
        """Clears transient battle flags but does NOT heal - wounds and
        corruption drain carry over from the overworld."""
        self.blocking = False
        self.shield = 0
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def full_heal(self):
        self.hp = self.max_hp_total
        self.alive = True

    def equip(self, item):
        slot = item.slot
        old = self.equipment[slot]
        self.equipment[slot] = item
        return old


class Party:
    def __init__(self, class_names, captain_index=0):
        self.members = [Character(c) for c in class_names]
        for m in self.members:
            m.party = self
        self.captain_index = captain_index
        self.members[captain_index].is_captain = True

    @property
    def captain(self):
        return self.members[self.captain_index]

    def followers(self):
        return [m for m in self.members if not m.is_captain]

    def alive_members(self):
        return [m for m in self.members if m.alive]

    def is_wiped(self):
        return not self.captain.alive

    def ready_for_battle(self):
        for m in self.members:
            m.ready_for_battle()

    def full_heal(self):
        for m in self.members:
            m.full_heal()

    def partial_heal(self, frac):
        for m in self.members:
            if m.alive:
                m.heal(round(m.max_hp_total * frac))
