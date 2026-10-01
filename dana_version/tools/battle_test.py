"""Headless battle demo: one party vs one enemy, printing every event.
Run from the dana_version folder:  python tools/battle_test.py [seed]"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.characters import PRESET_TEAMS  # noqa: E402
from data.enemies import ENEMIES  # noqa: E402
from game_state import RunState  # noqa: E402


def choose_action(state):
    member = state.current
    enemy = state.alive_enemies()[0]
    if enemy.intent["max_dmg"] >= 18 and state.guard_by is None:
        return {"kind": "block"}
    ok, _ = state.skill_status(member)
    if ok and member.char["skill"]["effect"] != "heal_leader":
        return {"kind": "skill", "target": enemy.uid}
    return {"kind": "attack", "target": enemy.uid}


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rng = random.Random(seed)
    run = RunState(PRESET_TEAMS[0]["members"], 0, rng)
    state = run.make_battle([ENEMIES["Goblin"]], can_flee=True)
    print(f"seed={seed}  party={[p.name for p in state.party]}  leader={state.leader.name}")
    for ev in state.start_events:
        print(ev["log"])
    while state.outcome is None:
        if state.current.side == "party":
            events = state.apply_action(choose_action(state))
        else:
            events = state.take_enemy_turn()
        for ev in events:
            print(ev["log"])
    print(f"\nOutcome: {state.outcome}  party actions: {state.party_actions}  "
          f"leader HP {state.leader_hp}/{state.leader_max_hp}  SP {state.sp}")


if __name__ == "__main__":
    main()
