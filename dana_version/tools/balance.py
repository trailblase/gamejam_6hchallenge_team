"""Auto-plays battles per encounter with a simple policy and prints win rate,
party actions per fight and leader HP lost. Targets from the spec: normal
fights ~4-7 party actions, bosses ~12-18.
Run from the dana_version folder:  python tools/balance.py [battles_per_encounter]"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.characters import PRESET_TEAMS  # noqa: E402
from data.enemies import ENEMIES, BOSSES  # noqa: E402
from data.world_map import ENEMY_GROUPS  # noqa: E402
from game_state import RunState  # noqa: E402

BIG_HIT = 18          # policy blocks big intents once the leader is below half HP
LOW_HP = 0.5


def policy(state):
    member = state.current
    enemies = state.alive_enemies()
    low = state.leader_hp < state.leader_max_hp * LOW_HP
    danger = any(e.charging for e in enemies) or (low and any(e.intent["max_dmg"] >= BIG_HIT for e in enemies))
    if danger and state.guard_by is None:
        return {"kind": "block"}
    skill = member.char["skill"]
    can_skill = state.skill_status(member)[0]
    weakest = min(enemies, key=lambda e: e.hp)
    if can_skill:
        if skill["effect"] == "heal_leader" and state.leader_hp <= state.leader_max_hp - skill["amount"]:
            return {"kind": "skill"}
        if skill["effect"] == "aoe_damage" and len(enemies) >= 2:
            return {"kind": "skill"}
        if skill["effect"] == "single_damage":
            return {"kind": "skill", "target": max(enemies, key=lambda e: e.hp).uid}
    return {"kind": "attack", "target": weakest.uid}


def simulate(defs, n, rewards=0, seed=0):
    wins = actions = hp_lost = 0
    for i in range(n):
        team = PRESET_TEAMS[i % 3]["members"]
        run = RunState(team, (i // 3) % 3, random.Random(seed * 100_000 + i))
        for _ in range(rewards):
            run.apply_reward(run.roll_rewards()[0])
        run.full_heal()
        start = run.leader_hp
        state = run.make_battle(defs, can_flee=False)
        while state.outcome is None:
            if state.current.side == "party":
                state.apply_action(policy(state))
            else:
                state.take_enemy_turn()
        wins += state.outcome == "victory"
        actions += state.party_actions
        hp_lost += start - state.leader_hp
    return wins / n, actions / n, hp_lost / n


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print(f"{'encounter':34s} {'win%':>6s} {'actions':>8s} {'HP lost':>8s}")
    for marker, group in ENEMY_GROUPS.items():
        w, a, h = simulate([ENEMIES[g] for g in group], n, seed=ord(marker))
        flag = "" if 4 <= a <= 7 else "   <-- outside 4-7"
        print(f"{marker}: {' + '.join(group):31s} {w * 100:5.0f}% {a:8.1f} {h:8.1f}{flag}")
    for rewards in (0, 4):
        for boss_id, boss in BOSSES.items():
            w, a, h = simulate([boss], n, rewards=rewards, seed=len(boss_id) + rewards)
            flag = "" if 12 <= a <= 18 else "   <-- outside 12-18"
            print(f"{boss['name'] + f' (+{rewards} rewards)':34s} {w * 100:5.0f}% {a:8.1f} {h:8.1f}{flag}")


if __name__ == "__main__":
    main()
