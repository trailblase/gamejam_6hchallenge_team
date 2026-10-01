"""Post-battle rewards (pick 1 of 3). Effects stack.
effect: atk_pct | leader_max_hp | max_sp | spd | heal"""

REWARDS = [
    {"id": "atk", "name": "Sharpened Resolve", "desc": "+10% party ATK",
     "effect": "atk_pct", "value": 0.10},
    {"id": "vigor", "name": "Hearty Stew", "desc": "+15 leader max HP, heal 15",
     "effect": "leader_max_hp", "value": 15},
    {"id": "focus", "name": "Focus Charm", "desc": "+1 max skill point",
     "effect": "max_sp", "value": 1},
    {"id": "boots", "name": "Light Boots", "desc": "+5 SPD to the party",
     "effect": "spd", "value": 5},
    {"id": "tea", "name": "Warm Tea", "desc": "Heal the leader 30",
     "effect": "heal", "value": 30},
]
