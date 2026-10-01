import random

WEAPON_NAMES = ["Rusty Blade", "Ember Edge", "Void Dagger", "Storm Lance", "Bone Cleaver"]
ARMOR_NAMES = ["Scrap Plate", "Hide Vest", "Corrupted Mail", "Sunward Shield", "Shadow Cloak"]
ACCESSORY_NAMES = ["Lucky Coin", "Cracked Charm", "Ember Ring", "Phase Amulet", "Void Shard"]


class Item:
    def __init__(self, slot, name, atk=0, hp=0, spd=0, block=0.0):
        self.slot = slot
        self.name = name
        self.atk = atk
        self.hp = hp
        self.spd = spd
        self.block = block

    def describe(self):
        parts = []
        if self.atk:
            parts.append(f"+{self.atk} ATK")
        if self.hp:
            parts.append(f"+{self.hp} HP")
        if self.spd:
            parts.append(f"+{self.spd} SPD")
        if self.block:
            parts.append(f"+{int(self.block*100)}% BLK")
        return " ".join(parts)


def random_item(level_index):
    power = 1 + level_index
    slot = random.choice(["weapon", "armor", "accessory"])
    if slot == "weapon":
        name = random.choice(WEAPON_NAMES)
        return Item("weapon", name, atk=random.randint(2, 3) * power)
    elif slot == "armor":
        name = random.choice(ARMOR_NAMES)
        if random.random() < 0.5:
            return Item("armor", name, hp=random.randint(4, 7) * power)
        return Item("armor", name, block=round(random.uniform(0.03, 0.06) * power, 2))
    else:
        name = random.choice(ACCESSORY_NAMES)
        return Item("accessory", name, spd=random.randint(1, 2) * power)


def best_recipient(party_members, item):
    def slot_score(member):
        current = member.equipment[item.slot]
        if current is None:
            return -1
        return current.atk + current.hp + current.spd + current.block * 10
    candidates = [m for m in party_members if m.alive]
    if not candidates:
        candidates = party_members
    return min(candidates, key=slot_score)
