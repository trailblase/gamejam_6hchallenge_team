"""Acceptance tests from the spec (section 9), run headlessly on the pure
logic. Run from the dana_version folder:  python tools/acceptance.py"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import config  # noqa: E402
from data.characters import PRESET_TEAMS  # noqa: E402
from data.enemies import ENEMIES, BOSSES  # noqa: E402
from data.world_map import ENEMY_GROUPS  # noqa: E402
from game_state import RunState  # noqa: E402
from overworld.world import World  # noqa: E402

PASSED = []


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAILED: {name}  {detail}")
    PASSED.append(name)
    print(f"  ok  {name}")


def new_run(seed, team=0, leader=0):
    return RunState(PRESET_TEAMS[team]["members"], leader, random.Random(seed))


def random_policy(state, rng):
    member = state.current
    targets = state.alive_enemies()
    choices = ["attack", "block"]
    if state.skill_status(member)[0]:
        choices.append("skill")
    kind = rng.choice(choices)
    return {"kind": kind, "target": rng.choice(targets).uid}


def run_battle(state, policy, on_events=None, max_steps=2000):
    if on_events:
        on_events(state.start_events)
    steps = 0
    while state.outcome is None and steps < max_steps:
        steps += 1
        if state.current.side == "party":
            events = state.apply_action(policy(state))
        else:
            events = state.take_enemy_turn()
        if on_events:
            on_events(events)
    return steps


def main():
    print("1. only the leader is ever targeted; followers have no HP")
    leader_hits = other_hits = 0
    for seed in range(60):
        run = new_run(seed, team=seed % 3, leader=seed % 3)
        group = list(ENEMY_GROUPS.values())[seed % len(ENEMY_GROUPS)]
        state = run.make_battle([ENEMIES[n] for n in group], can_flee=True)
        prng = random.Random(seed + 1000)
        enemy_ids = {e.uid for e in state.enemies}

        def tally(events):
            nonlocal leader_hits, other_hits
            for ev in events:
                if ev["type"] in ("damage", "blocked") and ev.get("source") in enemy_ids:
                    if ev["uid"] == state.leader.uid:
                        leader_hits += 1
                    else:
                        other_hits += 1

        run_battle(state, lambda s: random_policy(s, prng), tally)
        followers = [p for p in state.party if not p.is_leader]
        assert all(not hasattr(p, "hp") for p in followers)
    check("enemy attacks only hit the leader", other_hits == 0 and leader_hits > 0,
          f"leader {leader_hits} other {other_hits}")
    check("followers have no HP attribute", True)

    print("2. block negates all damage until that member's next turn, no stacking")
    blocked_total = leaked = 0
    for seed in range(40):
        run = new_run(seed)
        run.leader_hp_bonus = 10_000
        run.full_heal()
        state = run.make_battle([ENEMIES["Goblin"], ENEMIES["Slime"]], can_flee=True)
        guarding = {"uid": None}

        def watch(events):
            nonlocal blocked_total, leaked
            for ev in events:
                if ev["type"] == "guard":
                    guarding["uid"] = ev["uid"]
                elif ev["type"] == "guard_end":
                    guarding["uid"] = None
                elif ev["type"] == "damage" and ev["uid"] == state.leader.uid and guarding["uid"]:
                    leaked += 1
                elif ev["type"] == "blocked":
                    blocked_total += 1
                    assert guarding["uid"] is not None

        steps = 0
        watch(state.start_events)
        while state.outcome is None and steps < 200:
            steps += 1
            if state.current.side == "party":
                ev = state.apply_action({"kind": "block"})
            else:
                ev = state.take_enemy_turn()
            watch(ev)
            assert state.guard_by is None or isinstance(state.guard_by, str)
    check("no damage leaks through an active guard", leaked == 0 and blocked_total > 0,
          f"leaked {leaked} blocked {blocked_total}")
    run = new_run(3)
    state = run.make_battle([ENEMIES["Slime"]], can_flee=True)
    while state.current.side != "party":
        state.take_enemy_turn()
    first = state.current.uid
    state.apply_action({"kind": "block"})
    while state.current.side != "party":
        state.take_enemy_turn()
    second = state.current.uid
    state.apply_action({"kind": "block"})
    check("block does not stack (one guard owner at a time)", state.guard_by in (first, second))

    print("3. skill gated by SP; SP stays within 0..max")
    run = new_run(5)
    state = run.make_battle([ENEMIES["Goblin"]], can_flee=True)
    while state.current.side != "party":
        state.take_enemy_turn()
    state.sp = 0
    ok, reason = state.skill_status(state.current)
    raised = False
    try:
        state.apply_action({"kind": "skill"})
    except ValueError:
        raised = True
    check("skill disabled with a reason at 0 SP", not ok and "SP" in reason and raised, reason)
    sp_ok = True
    for seed in range(80):
        run = new_run(seed, team=seed % 3)
        run.max_sp_bonus = seed % 3
        state = run.make_battle([ENEMIES["Goblin"], ENEMIES["Mossling"]], can_flee=True)
        prng = random.Random(seed)

        def sp_watch(events, st=state):
            nonlocal sp_ok
            if not (0 <= st.sp <= st.max_sp):
                sp_ok = False

        run_battle(state, lambda s: random_policy(s, prng), sp_watch)
    check("SP never below 0 or above max", sp_ok)

    print("4. faster units act more often; timeline matches reality")
    run = new_run(9, team=0)   # Warrior 100, Mage 104, Rogue 112
    run.leader_hp_bonus = 100_000
    run.full_heal()
    dummy = dict(ENEMIES["Slime"], max_hp=100_000, spd=80)
    state = run.make_battle([dummy], can_flee=True)
    counts = {}
    for _ in range(600):
        counts[state.current.name] = counts.get(state.current.name, 0) + 1
        if state.current.side == "party":
            state.apply_action({"kind": "block"})
        else:
            state.take_enemy_turn()
    check("speed ordering of action counts (Rogue > Mage > Warrior > Slime)",
          counts["Rogue"] > counts["Mage"] > counts["Warrior"] > counts["Slime"], str(counts))
    mismatches = 0
    for _ in range(50):
        predicted = state.timeline()
        actual = [state.current.uid]
        for _ in range(len(predicted) - 1):
            if state.current.side == "party":
                state.apply_action({"kind": "block"})
            else:
                state.take_enemy_turn()
            actual.append(state.current.uid)
        if predicted != actual:
            mismatches += 1
    check("timeline preview == actual turn order", mismatches == 0, f"{mismatches} mismatches")

    print("5. enemy damage within range and varies between runs")
    rolls = {}
    in_range = True
    for seed in range(200):
        run = new_run(seed)
        run.leader_hp_bonus = 10_000
        run.full_heal()
        state = run.make_battle([ENEMIES["Goblin"]], can_flee=True)

        def roll_watch(events):
            nonlocal in_range
            for ev in events:
                if ev["type"] == "damage" and ev["uid"] == state.leader.uid:
                    a = ev["attack"]
                    if not a["min_dmg"] <= ev["amount"] <= a["max_dmg"]:
                        in_range = False
                    rolls.setdefault(a["name"], set()).add(ev["amount"])

        run_battle(state, lambda s: {"kind": "attack"}, roll_watch)
    check("every hit within min..max", in_range)
    check("damage varies", all(len(v) > 3 for v in rolls.values()), str({k: sorted(v) for k, v in rolls.items()}))

    print("6. charged boss attacks are telegraphed and blockable")
    for boss_id, boss in BOSSES.items():
        telegraphed = landed_blocked = charge_seen = 0
        twice_in_row = False
        early_charge = False
        for seed in range(40):
            run = new_run(seed)
            run.leader_hp_bonus = 50_000
            run.full_heal()
            state = run.make_battle([boss], can_flee=False)
            b = state.enemies[0]
            last_kind = {"charged": False}
            prev = {"intent_charged": False}

            def boss_watch(events):
                nonlocal telegraphed, charge_seen, early_charge, twice_in_row
                for ev in events:
                    if ev["type"] == "intent" and ev["attack"].get("charged"):
                        if not b.phase2:
                            early_charge = True
                        if last_kind["charged"]:
                            twice_in_row = True
                    if ev["type"] == "charge_start":
                        charge_seen += 1
                        if prev["intent_charged"]:
                            telegraphed += 1
                    if ev["type"] in ("damage", "blocked") and ev.get("source") == b.uid:
                        last_kind["charged"] = bool(ev["attack"].get("charged"))
                    if ev["type"] == "intent":
                        prev["intent_charged"] = bool(ev["attack"].get("charged"))

            def policy(s):
                if b.charging:
                    return {"kind": "block"}
                return {"kind": "attack"}

            def counting(events):
                nonlocal landed_blocked
                boss_watch(events)
                for ev in events:
                    if ev["type"] == "blocked" and ev["attack"].get("charged"):
                        landed_blocked += 1

            run_battle(state, policy, counting)
        check(f"{boss['name']}: charge shown in intent before it starts", charge_seen > 0 and
              telegraphed == charge_seen, f"seen {charge_seen} telegraphed {telegraphed}")
        check(f"{boss['name']}: charged hit blocked when guarding", landed_blocked > 0)
        check(f"{boss['name']}: no charge above 50% HP or twice in a row", not early_charge and not twice_in_row)

    print("7. world: defeated never return, fled return after stun, boss counts once")
    rng = random.Random(1)
    run = new_run(1)
    world = World(rng, run.defeated, run.springs_used)
    normal = next(e for e in world.enemies if not e.is_boss)
    run.record_defeat(normal.id)
    world.remove_enemy(normal.id)
    world.respawn_player(config.WINDOW_W, config.WINDOW_H)
    world2 = World(rng, run.defeated, run.springs_used)
    check("defeated enemy gone from world and from a rebuilt world",
          all(e.id != normal.id for e in world.enemies) and all(e.id != normal.id for e in world2.enemies))
    fled = next(e for e in world.enemies if not e.is_boss)
    world.player.x, world.player.y = fled.x, fled.y
    world.stun_enemy(fled.id)
    touched_during_stun = False
    for _ in range(int(config.FLEE_STUN_SECONDS * 60) - 5):
        if world.update(1 / 60, 0, 0, config.WINDOW_W, config.WINDOW_H) is fled:
            touched_during_stun = True
    after = None
    for _ in range(30):
        after = after or world.update(1 / 60, 0, 0, config.WINDOW_W, config.WINDOW_H)
    check("stunned enemy can't start a fight, then can again", not touched_during_stun and after is fled)
    boss = next(e for e in world.enemies if e.is_boss)
    run.record_defeat(boss.id, boss.key)
    run.record_defeat(boss.id, boss.key)
    check("boss counted once", len(run.bosses_defeated) == 1)

    print("8/9. retry keeps defeats; 3 bosses -> win condition")
    run.leader_hp = 0
    run.retry()
    check("retry restores full HP and keeps defeats",
          run.leader_hp == run.leader_max_hp and boss.id in run.defeated and normal.id in run.defeated)
    for e in list(world.enemies):
        if e.is_boss:
            run.record_defeat(e.id, e.key)
    check("all 3 bosses -> win", run.all_bosses_defeated and len(run.bosses_defeated) == config.BOSSES_TO_WIN)

    print("10. 20+ battles in a row without crashing")
    run = new_run(77)
    prng = random.Random(77)
    fought = 0
    for i in range(40):
        group = list(ENEMY_GROUPS.values())[i % len(ENEMY_GROUPS)]
        defs = [BOSSES[list(BOSSES)[i % 3]]] if i % 7 == 6 else [ENEMIES[n] for n in group]
        state = run.make_battle(defs, can_flee=True)
        run_battle(state, lambda s: random_policy(s, prng))
        run.finish_battle(state)
        if state.outcome == "victory":
            run.apply_reward(run.roll_rewards()[0])
            run.victory_heal()
        if run.leader_hp <= 0:
            run.retry()
        fought += 1
    check("40 consecutive battles", fought == 40)

    corruption_checks()
    print(f"\nALL {len(PASSED)} ACCEPTANCE CHECKS PASSED")


def corruption_checks():
    import math
    from data.buffs import BUFFS
    from data.chests import CHESTS
    from overworld.world import check_reachability

    print("11. overworld corruption, chests and buffs")
    world = World(random.Random(5))
    c = world.corruption
    start = world.start_tile
    check("start seeds placed", c.count == config.CORRUPT_START_SEEDS, str(c.count))
    seeds = [(x, y) for y in range(c.h) for x in range(c.w) if c.grid[y][x]]
    check("no seed within 3 tiles of the start",
          all(max(abs(x - start[0]), abs(y - start[1])) > config.CORRUPT_SEED_MIN_START_DIST for x, y in seeds))
    guarded = [ch["tile"] for ch in CHESTS if ch["guarded"]]
    check("a corruption seed sits by the guarded chest",
          all(any(max(abs(x - gx), abs(y - gy)) <= config.CORRUPT_GUARD_RADIUS for x, y in seeds)
              for gx, gy in guarded))

    steps = 0
    while not c.capped and steps < 2000:
        c.spread_step()
        steps += 1
    total = sum(sum(row) for row in c.grid)
    check(f"spread stops at the cap ({c.cap} tiles = {config.CORRUPT_MAX_FRACTION:.0%} of walkable)",
          c.capped and total == c.count == c.cap, f"count {c.count} grid {total} cap {c.cap} after {steps} steps")
    before = c.count
    c.spread_step()
    check("no growth past the cap", c.count == before)
    bad = [(x, y) for y in range(c.h) for x in range(c.w)
           if c.grid[y][x] and world.map.kind(x, y) not in ("grass", "flowers")]
    check("paths, water, trees and bushes never corrupt", not bad, str(bad[:5]))
    boss_tiles = [t for ch in "XYZ" for t in world.map.markers.get(ch, [])]
    in_arena = [(x, y) for y in range(c.h) for x in range(c.w) if c.grid[y][x] and
                any(max(abs(x - bx), abs(y - by)) <= config.CORRUPT_ARENA_RADIUS for bx, by in boss_tiles)]
    check("boss arenas never corrupt", not in_arena, str(in_arena[:5]))

    w1, w2 = World(random.Random(11)), World(random.Random(11))
    for _ in range(30):
        w1.force_spread()
        w2.force_spread()
    check("same seed -> same corruption", w1.corruption.grid == w2.corruption.grid)

    targets = {f"chest {ch['id']}": ch["tile"] for ch in CHESTS}
    check("map flood-fill reaches every chest/enemy/boss/spring", world.reachable_tiles > 0)
    try:
        check_reachability(world.map, start, {"inside a tree": (0, 0)})
        caught = False
    except AssertionError:
        caught = True
    check("flood-fill check catches an unreachable target", caught and bool(targets))

    world = World(random.Random(6))
    tile = next((x, y) for y in range(world.corruption.h) for x in range(world.corruption.w)
                if world.corruption.grid[y][x])
    world.player.x, world.player.y = tile[0] * config.TILE + config.TILE / 2, tile[1] * config.TILE + 20
    check("leader standing on corruption counts as slowed", world.leader_slowed)
    x0 = world.player.x
    world.update(0.05, 1, 0, config.WINDOW_W, config.WINDOW_H)
    step = world.player.x - x0
    expected = config.PLAYER_SPEED * 0.05 * config.CORRUPT_SLOW
    check("slowed step == PLAYER_SPEED * CORRUPT_SLOW", math.isclose(step, expected, abs_tol=0.01),
          f"step {step:.2f} expected {expected:.2f}")

    chest = world.chests[0]
    world.player.x, world.player.y = chest.x, chest.y + 8
    first = world.open_chest()
    second = world.open_chest()
    check("chest opens once", first is chest and second is None and chest.opened)

    by_id = {b["id"]: b for b in BUFFS}
    from data.characters import CHARACTERS
    run = new_run(2)
    run.apply_buff(by_id["sharpened"])
    buffed = [s["atk"] for s in run.party_specs()]
    expected_atk = [round(CHARACTERS[k]["atk"] * 1.2) for k in run.team]
    check("Sharpened: +20% party ATK", buffed == expected_atk, f"{buffed} vs {expected_atk}")
    run.apply_buff(by_id["focus"])
    st = run.make_battle([ENEMIES["Slime"]], can_flee=True)
    check("Focus: battle starts with +2 SP", st.sp == min(config.START_SP + 2, st.max_sp), str(st.sp))
    run.apply_buff(by_id["ward"])
    st = run.make_battle([dict(ENEMIES["Goblin"], max_hp=10_000)], can_flee=True)
    hits = []
    while st.outcome is None and len(hits) < 2:
        if st.current.side == "party":
            ev = st.apply_action({"kind": "attack"})
        else:
            ev = st.take_enemy_turn()
        hits += [e for e in ev if e["type"] in ("damage", "blocked") and e["uid"] == st.leader.uid]
    check("Ward: first enemy hit blocked, second lands",
          len(hits) >= 2 and hits[0]["type"] == "blocked" and hits[0].get("ward") and hits[1]["type"] == "damage",
          str([(h["type"], h.get("ward")) for h in hits]))
    run.leader_hp = 10
    run.apply_buff(by_id["mend"])
    check("Mend: heals 25% max HP", run.leader_hp == 10 + round(run.leader_max_hp * 0.25), str(run.leader_hp))
    plain = new_run(2).make_battle([ENEMIES["Slime"]], can_flee=True)
    check("no buffs -> engine unchanged (3 SP, no ward)", plain.sp == config.START_SP and plain.ward == 0)


if __name__ == "__main__":
    main()
