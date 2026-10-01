"""Drives the real scenes headlessly (no window) through the whole game:
title -> team -> leader -> overworld -> battles (win, flee, defeat, retry)
-> all bosses -> win screen. Catches crashes in drawing and flow code.
Run from the dana_version folder:  python tools/smoke_scenes.py"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from main import App  # noqa: E402

DT = 1 / 60
held = set()


class _Keys:
    def __getitem__(self, k):
        return k in held


pygame.key.get_pressed = lambda: _Keys()


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def frames(app, n, events=()):
    for i in range(n):
        app.tick(DT, list(events) if i == 0 else [])


def wait_for(app, cls_name, limit=600):
    for _ in range(limit):
        if type(app.state).__name__ == cls_name:
            return
        frames(app, 1)
    raise AssertionError(f"never reached {cls_name}, stuck in {type(app.state).__name__}")


def play_battle(app, choose):
    """Feed keys whenever the battle waits for input until it leaves."""
    for _ in range(20000):
        st = app.state
        if type(st).__name__ != "BattleScene":
            return
        if st.mode == "menu":
            frames(app, 1, [key(choose(st))])
        elif st.mode == "target":
            frames(app, 1, [key(pygame.K_RETURN)])
        elif st.mode == "reward":
            frames(app, 1, [key(pygame.K_2)])
        else:
            frames(app, 1)
    raise AssertionError("battle never ended")


def attack_or_skill(st):
    ok, _ = st.engine.skill_status(st.engine.current)
    return pygame.K_2 if ok else pygame.K_1


def main():
    app = App(seed=42)
    frames(app, 5)
    app.debug = True
    frames(app, 2, [key(pygame.K_RETURN)])
    wait_for(app, "TeamSelectScene")
    frames(app, 2, [key(pygame.K_RIGHT)])
    frames(app, 2, [key(pygame.K_RETURN)])
    wait_for(app, "LeaderSelectScene")
    frames(app, 2, [key(pygame.K_RETURN)])
    wait_for(app, "OverworldScene")
    ow = app.state
    print("reached overworld; team", app.run.team, "leader", app.run.leader_key)

    # walk around (diagonal + into walls)
    start = (ow.world.player.x, ow.world.player.y)
    held.update({pygame.K_d, pygame.K_s})
    frames(app, 40)
    held.clear()
    held.add(pygame.K_LEFT)
    frames(app, 120)
    held.clear()
    moved = (ow.world.player.x, ow.world.player.y) != start
    print("player moved:", moved)
    assert moved

    # normal fight -> win via real menu input
    enemy = next(e for e in ow.world.enemies if not e.is_boss)
    ow._start_battle(enemy)
    wait_for(app, "BattleScene")
    play_battle(app, attack_or_skill)
    wait_for(app, "OverworldScene")
    assert enemy.id in app.run.defeated
    print("won normal fight; leader HP", app.run.leader_hp)

    # flee from a fight
    enemy = next(e for e in ow.world.enemies if not e.is_boss)
    hp_before = app.run.leader_hp
    ow._start_battle(enemy)
    wait_for(app, "BattleScene")
    play_battle(app, lambda st: pygame.K_4)
    wait_for(app, "OverworldScene")
    assert enemy.stun > 0 and enemy.id not in app.run.defeated
    print(f"fled: HP {hp_before} -> {app.run.leader_hp}, enemy stunned {enemy.stun:.1f}s")

    # disabled skill shows a reason (drain SP first)
    enemy = next(e for e in ow.world.enemies if not e.is_boss)
    ow._start_battle(enemy)
    wait_for(app, "BattleScene")
    st = app.state
    st.engine.sp = 0
    for _ in range(600):
        if st.mode == "menu":
            break
        frames(app, 1)
    frames(app, 1, [key(pygame.K_2)])
    assert st.mode == "menu" and st.reason_timer > 0, (st.mode, st.reason)
    print("skill disabled reason:", st.reason)

    # defeat -> game over -> retry
    app.run.leader_hp = 1
    st.engine.leader_hp = 1
    play_battle(app, lambda st: pygame.K_1)
    name = type(app.state).__name__
    if name != "GameOverScene":
        wait_for(app, "GameOverScene", 2000)
    frames(app, 3)
    frames(app, 2, [key(pygame.K_RETURN)])
    wait_for(app, "OverworldScene")
    assert app.run.leader_hp == app.run.leader_max_hp
    print("game over + retry ok, HP", app.run.leader_hp)

    # spring
    spring = ow.world.springs[0]
    ow.world.player.x, ow.world.player.y = spring.x, spring.y + 10
    app.run.leader_hp = 10
    frames(app, 2, [key(pygame.K_e)])
    assert spring.used and app.run.leader_hp == app.run.leader_max_hp
    print("spring ok")

    # one real boss fight through the menu, with blocking against charges
    def boss_policy(st):
        e = st.engine
        if any(en.alive and en.charging for en in e.enemies) and e.guard_by is None:
            return pygame.K_3
        return attack_or_skill(st)

    frames(app, 2, [key(pygame.K_F3)])
    boss = next(e for e in ow.world.enemies if e.is_boss)
    app.run.leader_hp_bonus += 400   # make the scripted boss fight survivable
    app.run.full_heal()
    ow._start_battle(boss)
    wait_for(app, "BattleScene")
    play_battle(app, boss_policy)
    frames(app, 60)
    print("boss fight result: bosses", sorted(app.run.bosses_defeated), "state", type(app.state).__name__)

    # remaining bosses via F2 debug win -> win screen
    for _ in range(10):
        if type(app.state).__name__ == "WinScene":
            break
        if type(app.state).__name__ == "OverworldScene":
            frames(app, 2, [key(pygame.K_F3)])
            target = next((e for e in ow.world.enemies if e.is_boss), None)
            if target is None:
                break
            ow._start_battle(target)
            wait_for(app, "BattleScene")
            frames(app, 2, [key(pygame.K_F2)])
            play_battle(app, attack_or_skill)
        frames(app, 30)
    wait_for(app, "WinScene", 1200)
    print("reached WinScene with bosses", sorted(app.run.bosses_defeated))
    frames(app, 2, [key(pygame.K_RETURN)])
    wait_for(app, "TitleScene")
    print("SCENE SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
