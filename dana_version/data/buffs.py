"""Chest buffs. Each is a modifier dict; RunState sums active buffs into the
battle modifiers the engine reads at battle start. Buffs last the session
and stack if the same one is found twice.

modifier keys:
  atk_pct   - added to party ATK multiplier (0.20 = +20%)
  start_sp  - extra SP at battle start (still capped at max SP)
  ward      - enemy hits on the leader auto-blocked per battle
  heal_pct  - instant leader heal (share of max HP) when the chest opens"""

BUFFS = [
    {"id": "sharpened", "name": "Sharpened", "desc": "+20% party ATK", "mod": {"atk_pct": 0.20}},
    {"id": "focus", "name": "Focus", "desc": "Start battles with +2 SP", "mod": {"start_sp": 2}},
    {"id": "ward", "name": "Ward", "desc": "First enemy hit each battle is blocked", "mod": {"ward": 1}},
    {"id": "mend", "name": "Mend", "desc": "Heal the leader 25% max HP", "mod": {"heal_pct": 0.25}},
]
