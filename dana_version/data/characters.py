"""Playable characters. Names and stat ordering come from the original
Warrior / Paladin / Mage / Rogue data, rescaled to the new battle system.
`color` is a palette key (see ui/draw.py). Only the LEADER uses max_hp."""

CHARACTERS = {
    "Warrior": {
        "name": "Warrior", "color": "peach_dark", "max_hp": 130, "atk": 14, "spd": 100,
        "basic_attack": {"name": "Strike", "multiplier": 1.0},
        "skill": {"name": "Cleave", "sp_cost": 1, "effect": "aoe_damage", "multiplier": 0.7,
                  "desc": "0.7x damage to ALL enemies"},
    },
    "Paladin": {
        "name": "Paladin", "color": "gold", "max_hp": 135, "atk": 10, "spd": 96,
        "basic_attack": {"name": "Smite", "multiplier": 1.0},
        "skill": {"name": "Mend", "sp_cost": 1, "effect": "heal_leader", "amount": 22,
                  "desc": "Heal the leader for 22"},
    },
    "Mage": {
        "name": "Mage", "color": "blue", "max_hp": 90, "atk": 18, "spd": 104,
        "basic_attack": {"name": "Spark", "multiplier": 1.0},
        "skill": {"name": "Bolt", "sp_cost": 1, "effect": "single_damage", "multiplier": 2.0,
                  "desc": "2.0x damage to one enemy"},
    },
    "Rogue": {
        "name": "Rogue", "color": "sage_dark", "max_hp": 100, "atk": 13, "spd": 112,
        "basic_attack": {"name": "Stab", "multiplier": 1.0},
        "skill": {"name": "Backstab", "sp_cost": 1, "effect": "single_damage", "multiplier": 1.7,
                  "desc": "1.7x damage to one enemy"},
    },
}

PRESET_TEAMS = [
    {"name": "Vanguard", "members": ["Warrior", "Mage", "Rogue"]},
    {"name": "Swift Hands", "members": ["Paladin", "Mage", "Rogue"]},
    {"name": "Old Guard", "members": ["Warrior", "Paladin", "Mage"]},
]
