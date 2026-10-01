"""Enemy and boss data. Attack fields:
  name, min_dmg, max_dmg, weight   - weighted random intent choice
  phase2_weight (optional)          - weight once a boss drops below half HP
  charged (optional)                - boss spends one turn charging, lands next turn
  heal_self_pct (optional)          - attacker heals this share of its max HP
  lifesteal (optional)              - attacker heals by the damage it dealt
`color` is a palette key, `size` is the body width in battle (px)."""

ENEMIES = {
    "Slime": {
        "name": "Slime", "max_hp": 42, "spd": 90, "color": "sage", "size": 44,
        "attacks": [
            {"name": "Nibble", "min_dmg": 6, "max_dmg": 10, "weight": 1},
        ],
    },
    "Mossling": {
        "name": "Mossling", "max_hp": 56, "spd": 95, "color": "lavender", "size": 48,
        "attacks": [
            {"name": "Spore Puff", "min_dmg": 7, "max_dmg": 11, "weight": 2},
            {"name": "Thorn Jab", "min_dmg": 12, "max_dmg": 17, "weight": 1},
        ],
    },
    "Goblin": {
        "name": "Goblin", "max_hp": 82, "spd": 100, "color": "pink", "size": 50,
        "attacks": [
            {"name": "Slash", "min_dmg": 10, "max_dmg": 16, "weight": 3},
            {"name": "Heavy Swing", "min_dmg": 18, "max_dmg": 26, "weight": 1},
        ],
    },
}

BOSSES = {
    "rot_guardian": {
        "name": "Rot Guardian", "max_hp": 260, "spd": 130, "color": "sage_dark", "size": 96,
        "is_boss": True, "phase_text": "The Rot Guardian's bark splits open!",
        "attacks": [
            {"name": "Strike", "min_dmg": 22, "max_dmg": 30, "weight": 3, "phase2_weight": 1},
            {"name": "Crush", "min_dmg": 33, "max_dmg": 42, "weight": 1, "phase2_weight": 2},
            {"name": "Doom Slam", "min_dmg": 45, "max_dmg": 60, "weight": 0, "phase2_weight": 2,
             "charged": True},
        ],
    },
    "ember_matron": {
        "name": "Ember Matron", "max_hp": 240, "spd": 136, "color": "peach_dark", "size": 90,
        "is_boss": True, "phase_text": "The Ember Matron flares white-hot!",
        "attacks": [
            {"name": "Flame Lash", "min_dmg": 20, "max_dmg": 27, "weight": 3, "phase2_weight": 1},
            {"name": "Cinder Rain", "min_dmg": 29, "max_dmg": 37, "weight": 1, "phase2_weight": 2},
            {"name": "Rekindle", "min_dmg": 11, "max_dmg": 15, "weight": 1, "phase2_weight": 2,
             "heal_self_pct": 0.10},
            {"name": "Inferno", "min_dmg": 50, "max_dmg": 64, "weight": 0, "phase2_weight": 2,
             "charged": True},
        ],
    },
    "hollow_king": {
        "name": "Hollow King", "max_hp": 270, "spd": 124, "color": "lavender_dark", "size": 100,
        "is_boss": True, "phase_text": "The Hollow King's crown cracks...",
        "attacks": [
            {"name": "Rend", "min_dmg": 24, "max_dmg": 32, "weight": 3, "phase2_weight": 1},
            {"name": "Soul Drain", "min_dmg": 19, "max_dmg": 26, "weight": 1, "phase2_weight": 2,
             "lifesteal": True},
            {"name": "Eclipse", "min_dmg": 55, "max_dmg": 70, "weight": 0, "phase2_weight": 2,
             "charged": True},
        ],
    },
}
