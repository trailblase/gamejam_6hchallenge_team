"""Battle presentation + input. Asks the engine for events and plays them
back as animations. Never decides a game rule itself."""

import math
from collections import deque

import pygame

from data import config
from battle.auto import choose_action, choose_reward
from game_state import RunState
from ui import audio
from ui import draw as D
from ui import sprites as S
from ui.weather import draw_corruption_weather

W, H = config.WINDOW_W, config.WINDOW_H
FLOOR_RECT = pygame.Rect(0, 0, 880, 220)
FLOOR_RECT.center = (W // 2, 340)
LEADER_POS = (345, 368)
FOLLOWER_POS = [(240, 300), (205, 398)]
LEADER_SIZE = (70, 78)
FOLLOWER_SIZE = (56, 62)
ENEMY_SLOTS = {
    1: [(690, 345)],
    2: [(640, 300), (790, 360)],
    3: [(610, 280), (735, 360), (860, 285)],
}
TIMELINE_RECT = pygame.Rect(0, 0, 460, 62)
TIMELINE_RECT.midtop = (W // 2, 10)
LEADER_PANEL = pygame.Rect(14, H - 112, 340, 98)
MENU_PANEL = pygame.Rect(W - 314, H - 190, 300, 178)
MENU_ROW_H = 28
HEAVY_HIT = 18          # intents at or above this max damage get the "heavy" color
SHAKE_SECONDS = 0.22
SHAKE_PIXELS = 5
LUNGE_SECONDS = 0.28
LUNGE_PIXELS = 26
BANNER_SECONDS = 1.3
REASON_SECONDS = 1.6
CARD_W, CARD_H = 220, 160


class UnitView:
    def __init__(self, unit, pos, size, hp=None, max_hp=None):
        self.uid = unit.uid
        self.name = unit.name
        self.color = unit.color
        self.side = unit.side
        self.x, self.y = pos
        self.w, self.h = size
        self.flash = 0.0
        self.squash = 0.0
        self.lunge = 0.0
        self.lunge_dir = 1
        self.dying = None
        self.dead = False
        self.bar = D.AnimatedBar(hp, max_hp) if hp is not None else None
        self.intent = None
        self.charging = False
        self.phase_offset = (pos[0] * 0.013) % math.tau

    def hit(self):
        self.flash = config.FLASH_SECONDS
        self.squash = config.HIT_SQUASH_SECONDS

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        self.squash = max(0.0, self.squash - dt)
        self.lunge = max(0.0, self.lunge - dt)
        if self.dying is not None and not self.dead:
            self.dying += dt
            if self.dying >= config.DEATH_FADE_SECONDS:
                self.dead = True
        if self.bar:
            self.bar.update(dt)

    @property
    def gone(self):
        return self.dead or self.dying is not None

    def lunge_offset(self):
        if self.lunge <= 0:
            return 0.0
        p = 1 - self.lunge / LUNGE_SECONDS
        return math.sin(p * math.pi) * LUNGE_PIXELS * self.lunge_dir


class Popup:
    def __init__(self, txt, x, y, col, size=26):
        self.txt, self.x, self.y, self.col, self.size = txt, x, y, col, size
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        return self.age < config.POPUP_SECONDS

    def draw(self, screen):
        p = self.age / config.POPUP_SECONDS
        rise = D.ease_out_cubic(p) * config.POPUP_RISE
        alpha = int(255 * (1 - max(0.0, p - 0.55) / 0.45))
        D.text(screen, self.txt, self.size, self.col, (self.x, self.y - rise), anchor="center", alpha=alpha)


class BattleScene:
    def __init__(self, app, overworld, enemy_entity, snapshot):
        self.app = app
        self.run = app.run
        self.overworld = overworld
        self.entity = enemy_entity
        audio.play_music("battle")
        kind = "boss" if enemy_entity.is_boss else "normal"
        defs = RunState.enemy_defs_for(kind, enemy_entity.key)
        self.touched_corruption = self.run.touched_corruption
        self.engine = self.run.make_battle(defs, can_flee=not enemy_entity.is_boss)
        self.backdrop = self._make_backdrop(snapshot, overworld.world.corruption.fraction_of_cap)

        self.views = {}
        leader = self.engine.leader
        self.views[leader.uid] = UnitView(leader, LEADER_POS, LEADER_SIZE,
                                          self.engine.leader_hp, self.engine.leader_max_hp)
        followers = [p for p in self.engine.party if not p.is_leader]
        for unit, pos in zip(followers, FOLLOWER_POS):
            self.views[unit.uid] = UnitView(unit, pos, FOLLOWER_SIZE)
        slots = ENEMY_SLOTS[min(3, len(self.engine.enemies))]
        for unit, pos in zip(self.engine.enemies, slots):
            self.views[unit.uid] = UnitView(unit, pos, (unit.size, unit.size * 0.9), unit.hp, unit.max_hp)

        self.queue = deque(self.engine.start_events)
        self.event_timer = 0.0
        self.enemy_wait = 0.0
        self.mode = "events"        # events | menu | target | victory | reward | defeat | fled
        self.mode_timer = 0.0
        self.mode_age = 0.0
        self.menu_index = 0
        self.target_index = 0
        self.pending = None         # "attack" | "skill" while targeting
        self.reason = ""
        self.reason_timer = 0.0
        self.active_uid = None
        self.timeline = []
        self.sp = self.engine.sp
        self.max_sp = self.engine.max_sp
        self.guarded = False
        self.popups = []
        self.banner = ""
        self.banner_timer = 0.0
        self.shake = 0.0
        self.t = 0.0
        self.rewards = []
        self.reward_index = 0
        self.finished = False
        self.auto_battle = config.AUTO_BATTLE_DEFAULT
        self.auto_elapsed = 0.0
        self.result_recorded = False
        self.quick_outcome = None
        self.quick_reward = None
        self.quick_hp_after_battle = None
        self.quick_max_hp_after_battle = None
        self.quick_continue_rect = pygame.Rect(W // 2 - 105, H // 2 + 112, 210, 42)

        names = " + ".join(e.name for e in self.engine.enemies)
        print(f"[battle] {names}  vs  {[p.name for p in self.engine.party]} "
              f"(leader {leader.name}, HP {self.engine.leader_hp}/{self.engine.leader_max_hp})")
        if self.engine.is_boss_fight:
            self._banner(self.engine.enemies[0].name)

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _make_backdrop(snapshot, corruption_frac=0.0):
        small = pygame.transform.smoothscale(snapshot, (W // 10, H // 10))
        small = pygame.transform.smoothscale(small, (W // 4, H // 4))
        blurred = pygame.transform.smoothscale(small, (W, H))
        tint = pygame.Surface((W, H), pygame.SRCALPHA)
        tint.fill(D.with_alpha(D.PALETTE["cream"], 70))
        blurred.blit(tint, (0, 0))
        tint.fill(D.with_alpha(D.PALETTE["ink"], 70))
        blurred.blit(tint, (0, 0))
        purple = int(config.CORRUPT_BATTLE_TINT_MAX * max(0.0, min(1.0, corruption_frac)))
        if purple:
            tint.fill(D.with_alpha(D.PALETTE["plum"], purple))
            blurred.blit(tint, (0, 0))
        return blurred

    def _banner(self, txt):
        self.banner = txt
        self.banner_timer = BANNER_SECONDS

    def _popup(self, uid, txt, col, size=26):
        v = self.views[uid]
        self.popups.append(Popup(txt, v.x, v.y - v.h - 18, col, size))

    def _current_member(self):
        cur = self.engine.current
        return cur if cur is not None and cur.side == "party" else None

    def _targets(self):
        alive = [e for e in self.engine.enemies if e.alive]
        return sorted(alive, key=lambda e: self.views[e.uid].x)

    def _menu_rows(self):
        member = self._current_member()
        skill = member.char["skill"]
        skill_ok, skill_reason = self.engine.skill_status(member)
        flee_ok, flee_reason = self.engine.flee_status()
        return [
            ("attack", f"Attack  -  {member.char['basic_attack']['name']}", True,
             "Hit one enemy.  +1 SP"),
            ("skill", f"Skill  -  {skill['name']} ({skill['sp_cost']} SP)", skill_ok,
             skill["desc"] if skill_ok else skill_reason),
            ("block", "Block", True, "Leader takes 0 dmg until this member's next turn"),
            ("flee", "Flee", flee_ok,
             f"Escape. Leader loses {int(config.FLEE_HP_COST_PCT * 100)}% HP" if flee_ok else flee_reason),
        ]

    # -------------------------------------------------------------- events
    def _play(self, ev):
        print(ev["log"])
        kind = ev["type"]
        uid = ev.get("uid")
        view = self.views.get(uid)
        if kind == "turn_start":
            self.active_uid = uid
            self.timeline = ev["timeline"]
        elif kind == "damage":
            view.bar.set(ev["hp"], ev["max_hp"])
            view.hit()
            audio.play("hit")
            src = self.views.get(ev.get("source"))
            if src:
                src.lunge = LUNGE_SECONDS
                src.lunge_dir = 1 if src.side == "party" else -1
            self._popup(uid, f"-{ev['amount']}", "pink_dark" if view.side == "party" else "ink")
            if view.side == "party":
                self.shake = SHAKE_SECONDS
        elif kind == "blocked":
            audio.play("block")
            src = self.views.get(ev.get("source"))
            if src:
                src.lunge = LUNGE_SECONDS
                src.lunge_dir = -1
            self._popup(uid, "WARD" if ev.get("ward") else "BLOCKED", "plum" if ev.get("ward") else "blue_dark", 24)
        elif kind == "heal":
            view.bar.set(ev["hp"], ev["max_hp"])
            self._popup(uid, f"+{ev['amount']}", "sage_dark")
        elif kind == "enemy_heal":
            view.bar.set(ev["hp"], ev["max_hp"])
            self._popup(uid, f"+{ev['amount']}", "sage_dark")
        elif kind == "death":
            view.dying = 0.0
        elif kind == "phase_change":
            self._banner(ev["text"] or f"{view.name} grows furious!")
        elif kind == "charge_start":
            view.charging = True
            self._banner(f"{view.name} is charging {ev['attack']['name']}!")
        elif kind == "intent":
            view.intent = ev["attack"]
            view.charging = ev["charging"]
        elif kind == "guard":
            self.guarded = True
            audio.play("block")
            self._popup(uid, "GUARD", "blue_dark", 22)
        elif kind == "guard_end":
            self.guarded = False
        elif kind == "sp":
            self.sp, self.max_sp = ev["sp"], ev["max_sp"]
        elif kind == "flee":
            view.bar.set(ev["hp"], ev["max_hp"])
            audio.play("flee")
            if ev["amount"]:
                self._popup(uid, f"-{ev['amount']}", "pink_dark")
        self.event_timer = config.EVENT_SECONDS.get(kind, 0.2)

    def _submit(self, action):
        self.mode = "events"
        self.pending = None
        if action.get("kind") == "skill":
            audio.play("skill")
        self.queue.extend(self.engine.apply_action(action))

    # --------------------------------------------------------------- input
    def handle_event(self, event):
        if self.mode == "quick_summary":
            self._quick_summary_input(event)
            return
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_q
                and self.engine.outcome is None and self.mode in ("menu", "events", "target")):
            self._quick_resolve()
            return
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_a
                and self.engine.outcome is None and self.mode in ("menu", "events")):
            self.auto_battle = not self.auto_battle
            self.auto_elapsed = 0.0
            if self.auto_battle and self.mode == "menu":
                self.mode = "events"
            print(f"[battle] auto-battle {'ON' if self.auto_battle else 'OFF'}")
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2 and self.engine.outcome is None:
            print("[debug] F2: instant win")
            self.mode = "events"
            self.queue.extend(self.engine.debug_win())
            return
        if self.mode == "menu":
            self._menu_input(event)
        elif self.mode == "target":
            self._target_input(event)
        elif self.mode == "reward":
            self._reward_input(event)

    def _menu_input(self, event):
        rows = self._menu_rows()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(rows)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(rows)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._activate(self.menu_index)
            elif pygame.K_1 <= event.key <= pygame.K_4:
                self.menu_index = event.key - pygame.K_1
                self._activate(self.menu_index)
        elif event.type == pygame.MOUSEMOTION:
            idx = self._menu_row_at(event.pos)
            if idx is not None:
                self.menu_index = idx
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._menu_row_at(event.pos)
            if idx is not None:
                self.menu_index = idx
                self._activate(idx)

    def _menu_row_rect(self, i):
        return pygame.Rect(MENU_PANEL.x + 12, MENU_PANEL.y + 38 + i * MENU_ROW_H, MENU_PANEL.width - 24, MENU_ROW_H - 4)

    def _menu_row_at(self, pos):
        for i in range(4):
            if self._menu_row_rect(i).collidepoint(pos):
                return i
        return None

    def _activate(self, index):
        key, _, enabled, reason = self._menu_rows()[index]
        member = self._current_member()
        if not enabled:
            self.reason = reason
            self.reason_timer = REASON_SECONDS
            return
        if key == "attack":
            self._begin_target("attack")
        elif key == "skill":
            if member.char["skill"]["effect"] == "single_damage":
                self._begin_target("skill")
            else:
                self._submit({"kind": "skill"})
        elif key == "block":
            self._submit({"kind": "block"})
        elif key == "flee":
            self._submit({"kind": "flee"})

    def _begin_target(self, pending):
        targets = self._targets()
        if len(targets) == 1:
            self._submit({"kind": pending, "target": targets[0].uid})
            return
        self.pending = pending
        self.mode = "target"
        self.target_index = min(self.target_index, len(targets) - 1)

    def _target_input(self, event):
        targets = self._targets()
        if event.type == pygame.KEYDOWN:
            back = event.mod & pygame.KMOD_SHIFT
            if event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN) or (event.key == pygame.K_TAB and not back):
                self.target_index = (self.target_index + 1) % len(targets)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP) or (event.key == pygame.K_TAB and back):
                self.target_index = (self.target_index - 1) % len(targets)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._submit({"kind": self.pending, "target": targets[self.target_index].uid})
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.mode = "menu"
                self.pending = None
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for i, e in enumerate(targets):
                v = self.views[e.uid]
                if pygame.Rect(v.x - v.w / 2, v.y - v.h, v.w, v.h).collidepoint(event.pos):
                    self.target_index = i
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._submit({"kind": self.pending, "target": e.uid})
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self.mode = "menu"

    def _card_rect(self, i):
        gap = 24
        total = CARD_W * len(self.rewards) + gap * (len(self.rewards) - 1)
        x0 = (W - total) // 2
        return pygame.Rect(x0 + i * (CARD_W + gap), H // 2 - CARD_H // 2 + 20, CARD_W, CARD_H)

    def _reward_input(self, event):
        n = len(self.rewards)
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.reward_index = (self.reward_index - 1) % n
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.reward_index = (self.reward_index + 1) % n
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._take_reward(self.reward_index)
            elif pygame.K_1 <= event.key < pygame.K_1 + n:
                self._take_reward(event.key - pygame.K_1)
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for i in range(n):
                if self._card_rect(i).collidepoint(event.pos):
                    self.reward_index = i
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._take_reward(i)

    def _take_reward(self, i):
        reward = self.rewards[i]
        self.run.apply_reward(reward)
        self.run.victory_heal()
        print(f"[reward] {reward['name']} ({reward['desc']}); leader HP now "
              f"{self.run.leader_hp}/{self.run.leader_max_hp}")
        self._finish("victory")

    def _record_result(self):
        if not self.result_recorded:
            self.run.finish_battle(self.engine)
            self.result_recorded = True

    def _quick_resolve(self):
        """Resolve the remaining battle logic immediately, then show a recap."""
        if self.engine.outcome is not None:
            return
        self.mode = "quick_summary"
        self.queue.clear()
        self.event_timer = 0.0
        self.enemy_wait = 0.0
        steps = 0
        while self.engine.outcome is None and steps < 5000:
            if self.engine.current.side == "party":
                self.engine.apply_action(choose_action(self.engine))
            else:
                self.engine.take_enemy_turn()
            steps += 1
        if self.engine.outcome is None:
            self.mode = "events"
            self.queue.append({"type": "turn_start",
                               "log": "Quick battle paused: action limit reached.",
                               "uid": self.engine.current.uid,
                               "timeline": self.engine.timeline()})
            return

        self._record_result()
        self.quick_outcome = self.engine.outcome
        self.quick_hp_after_battle = self.run.leader_hp
        self.quick_max_hp_after_battle = self.run.leader_max_hp
        if self.quick_outcome == "victory":
            self.rewards = self.run.roll_rewards()
            self.quick_reward = choose_reward(self.rewards, self.run)
            self.run.apply_reward(self.quick_reward)
            self.run.victory_heal()
        print(f"[battle] quick result {self.quick_outcome}; HP "
              f"{self.quick_hp_after_battle}/{self.run.leader_max_hp}; "
              f"reward {self.quick_reward['name'] if self.quick_reward else 'none'}")

    def _quick_summary_input(self, event):
        if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self._finish(self.quick_outcome)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.quick_continue_rect.collidepoint(event.pos):
                self._finish(self.quick_outcome)

    def _finish(self, outcome):
        if self.finished:
            return
        self.finished = True
        self.overworld.on_battle_end(self.entity, outcome)

    # -------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        for v in self.views.values():
            v.update(dt)
        self.popups = [p for p in self.popups if p.update(dt)]
        self.banner_timer = max(0.0, self.banner_timer - dt)
        self.reason_timer = max(0.0, self.reason_timer - dt)
        self.shake = max(0.0, self.shake - dt)

        if self.mode in ("menu", "target", "reward", "quick_summary"):
            return
        if self.mode in ("victory", "defeat", "fled"):
            self.mode_timer -= dt
            self.mode_age += dt
            if self.mode_timer <= 0:
                if self.mode == "victory":
                    self.rewards = self.run.roll_rewards()
                    self.reward_index = 0
                    self.mode = "reward"
                else:
                    self._finish(self.mode)
            return

        if self.event_timer > 0:
            self.event_timer -= dt
            return
        if self.queue:
            self._play(self.queue.popleft())
            return

        outcome = self.engine.outcome
        if outcome:
            self._record_result()
            self.mode = outcome
            self.mode_age = 0.0
            self.mode_timer = {"victory": config.VICTORY_BANNER_SECONDS,
                               "defeat": config.DEFEAT_BANNER_SECONDS,
                               "fled": 0.1}[outcome]
            return
        if self.engine.current.side == "enemy":
            self.enemy_wait += dt
            if self.enemy_wait >= config.ENEMY_TURN_DELAY:
                self.enemy_wait = 0.0
                self.queue.extend(self.engine.take_enemy_turn())
        else:
            if self.auto_battle:
                self.mode = "events"
                self.auto_elapsed += dt
                if self.auto_elapsed >= config.AUTO_ACTION_DELAY:
                    self.auto_elapsed = 0.0
                    self._submit(choose_action(self.engine))
            else:
                self.auto_elapsed = 0.0
                self.mode = "menu"
                self.menu_index = 0

    # ---------------------------------------------------------------- draw
    def draw(self, screen):
        screen.blit(self.backdrop, (0, 0))
        ox = math.sin(self.t * 70) * SHAKE_PIXELS * (self.shake / SHAKE_SECONDS) if self.shake else 0
        self._draw_floor(screen)

        for v in sorted(self.views.values(), key=lambda v: v.y):
            if not v.dead:
                self._draw_unit(screen, v, ox)
        draw_corruption_weather(screen, self.overworld.world.corruption.fraction_of_cap, self.t)
        self._draw_auto_badge(screen)
        for v in self.views.values():
            if v.side == "enemy" and not v.gone:
                self._draw_enemy_info(screen, v)
        self._draw_turn_arrow(screen)
        self._draw_timeline(screen)
        self._draw_leader_panel(screen)
        if self.mode in ("menu", "target"):
            self._draw_menu(screen)
        for p in self.popups:
            p.draw(screen)
        self._draw_banner(screen)
        if self.mode == "victory":
            self._draw_center_banner(screen, "Victory!", "sage_dark")
        elif self.mode == "defeat":
            self._draw_center_banner(screen, "Defeated...", "pink_dark")
        elif self.mode == "reward":
            self._draw_rewards(screen)
        elif self.mode == "quick_summary":
            self._draw_quick_summary(screen)

    def _draw_auto_badge(self, screen):
        if self.touched_corruption:
            status = pygame.Rect(16, 16, 205, 30)
            D.panel(screen, status, radius=15, fill="cream", alpha=235, outline="plum")
            D.text(screen, "TOUCHED  ·  PARTY ATK -10%", 12, "plum",
                   status.center, anchor="center", shadow=False)
        rect = pygame.Rect(W - 204, 16, 188, 30)
        D.panel(screen, rect, radius=15, fill="cream", alpha=235,
                outline="sage_dark" if self.auto_battle else "ink_soft")
        label = ("AUTO ON  [A]   Q SKIP" if self.auto_battle
                 else "AUTO OFF  [A]   Q SKIP")
        D.text(screen, label, 11, "sage_dark" if self.auto_battle else "ink_soft",
               rect.center, anchor="center", shadow=False)

    def _draw_quick_summary(self, screen):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill(D.with_alpha(D.PALETTE["ink"], 155))
        screen.blit(veil, (0, 0))
        box = pygame.Rect(W // 2 - 270, H // 2 - 178, 540, 356)
        won = self.quick_outcome == "victory"
        D.panel(screen, box, radius=24, fill="cream", alpha=250,
                outline="sage_dark" if won else "pink_dark")
        D.text(screen, "QUICK BATTLE  ·  VICTORY" if won else "QUICK BATTLE  ·  DEFEAT",
               27, "sage_dark" if won else "pink_dark",
               (box.centerx, box.y + 38), anchor="center", shadow=False)
        D.text(screen, f"HP after battle: {self.quick_hp_after_battle}/"
                      f"{self.quick_max_hp_after_battle}", 19, "ink",
               (box.centerx, box.y + 100), anchor="center", shadow=False)
        if won and self.quick_reward:
            D.text(screen, "REWARD RECEIVED", 13, "ink_soft",
                   (box.centerx, box.y + 145), anchor="center", shadow=False)
            D.text(screen, self.quick_reward["name"], 22, "ink",
                   (box.centerx, box.y + 177), anchor="center", shadow=False)
            D.text(screen, self.quick_reward["desc"], 16, "ink_soft",
                   (box.centerx, box.y + 207), anchor="center", shadow=False)
            D.text(screen, f"HP after reward and rest: {self.run.leader_hp}/"
                          f"{self.run.leader_max_hp}", 16, "sage_dark",
                   (box.centerx, box.y + 241), anchor="center", shadow=False)
        else:
            D.text(screen, "No reward this time.", 17, "ink_soft",
                   (box.centerx, box.y + 177), anchor="center", shadow=False)

        D.panel(screen, self.quick_continue_rect, radius=16, fill="peach",
                outline="peach_dark")
        D.text(screen, "Continue   [Space]", 16, "ink",
               self.quick_continue_rect.center, anchor="center", shadow=False)

    def _draw_floor(self, screen):
        D.oval_shadow(screen, FLOOR_RECT.centerx, FLOOR_RECT.centery + 14, FLOOR_RECT.width, FLOOR_RECT.height, 60)
        tmp = pygame.Surface(FLOOR_RECT.size, pygame.SRCALPHA)
        pygame.draw.ellipse(tmp, D.with_alpha(D.PALETTE["cream"], 210), tmp.get_rect())
        pygame.draw.ellipse(tmp, D.with_alpha(D.PALETTE["grass"], 160), tmp.get_rect().inflate(-40, -26))
        pygame.draw.ellipse(tmp, D.with_alpha(D.PALETTE["ink_soft"], 90), tmp.get_rect(), 3)
        screen.blit(tmp, FLOOR_RECT.topleft)

    def _draw_unit(self, screen, v, shake_x):
        bob = math.sin(self.t * config.BOB_SPEED + v.phase_offset) * config.BOB_PIXELS
        x = v.x + v.lunge_offset() + (shake_x if v.side == "party" else 0)
        y = v.y
        scale, alpha = 1.0, 255
        if v.dying is not None:
            p = min(1.0, v.dying / config.DEATH_FADE_SECONDS)
            scale, alpha = 1 - 0.8 * p, int(255 * (1 - p))
        if v.charging:
            pulse = 0.5 + 0.5 * math.sin(self.t * 6)
            S.draw_glow(screen, x, y - v.h * 0.5, v.w * (1.0 + 0.25 * pulse), "pink_dark", 1.3)
        facing = 0.7 if v.side == "party" else -0.7
        S.draw_body(screen, x, y + bob * 0.4, v.w, v.h + bob, v.color, facing_x=facing,
                    squash=v.squash / config.HIT_SQUASH_SECONDS,
                    flash=v.flash / config.FLASH_SECONDS, alpha=alpha, scale=scale)
        if v.uid == self.engine.leader.uid:
            D.draw_round_rect(screen, (x - 7, y - v.h - 16 + bob, 14, 8), D.PALETTE["gold"], 4)
            if self.guarded:
                bubble = pygame.Rect(0, 0, v.w + 30, v.h + 30)
                bubble.midbottom = (x, y + 10)
                pulse = 0.5 + 0.5 * math.sin(self.t * 4)
                D.draw_round_rect(screen, bubble, D.with_alpha(D.PALETTE["blue_light"], int(70 + 40 * pulse)),
                                  bubble.width // 2)
                D.draw_round_rect(screen, bubble, D.with_alpha(D.PALETTE["blue_dark"], 160),
                                  bubble.width // 2, width=2)

    def _intent_text(self, v):
        a = v.intent
        rng_txt = f"{a['min_dmg']}-{a['max_dmg']}"
        if v.charging:
            return f"CHARGING: {a['name']} {rng_txt}", "pink_dark"
        if a.get("charged"):
            return f"{a['name']} {rng_txt}  (charge)", "lavender_dark"
        return f"{a['name']} {rng_txt}", ("pink_dark" if a["max_dmg"] >= HEAVY_HIT else "peach_dark")

    def _draw_enemy_info(self, screen, v):
        bar_rect = pygame.Rect(0, 0, max(70, v.w), 10)
        bar_rect.midtop = (v.x, v.y + 12)
        v.bar.draw(screen, bar_rect)
        D.text(screen, v.name, 13, "ink", (v.x, bar_rect.bottom + 10), anchor="center", shadow=False)
        if v.intent:
            txt, col = self._intent_text(v)
            img_w = D.font(14).size(txt)[0]
            pill = pygame.Rect(0, 0, img_w + 34, 24)
            pill.midbottom = (v.x, v.y - v.h - 14)
            alpha = 235
            if v.charging:
                alpha = int(190 + 60 * (0.5 + 0.5 * math.sin(self.t * 6)))
            D.draw_round_rect(screen, pill, D.with_alpha(D.PALETTE["cream"], alpha), 12)
            D.draw_round_rect(screen, pill, D.PALETTE[col], 12, width=2)
            pygame.draw.circle(screen, D.PALETTE[col], (pill.x + 13, pill.centery), 6)
            D.text(screen, txt, 14, col, (pill.x + 24, pill.centery), anchor="midleft", shadow=False)

    def _draw_turn_arrow(self, screen):
        if self.active_uid is None or self.engine.outcome:
            return
        v = self.views[self.active_uid]
        bob = math.sin(self.t * 5) * 5
        top = v.y - v.h - (52 if v.side == "enemy" else 30) + bob
        pts = [(v.x - 9, top - 12), (v.x + 9, top - 12), (v.x, top)]
        pygame.draw.polygon(screen, D.PALETTE["gold"], pts)
        pygame.draw.polygon(screen, D.PALETTE["ink"], pts, 2)

        if self.mode == "target":
            targets = self._targets()
            if targets:
                tv = self.views[targets[self.target_index % len(targets)].uid]
                ring = pygame.Rect(0, 0, tv.w + 26, 20)
                ring.center = (tv.x, tv.y)
                pygame.draw.ellipse(screen, D.PALETTE["gold"], ring, 3)
                ty = tv.y - tv.h - 46 + bob
                tpts = [(tv.x - 10, ty - 14), (tv.x + 10, ty - 14), (tv.x, ty)]
                pygame.draw.polygon(screen, D.PALETTE["pink_dark"], tpts)

    def _draw_timeline(self, screen):
        D.panel(screen, TIMELINE_RECT, radius=20)
        D.text(screen, "NEXT", 11, "ink_soft", (TIMELINE_RECT.x + 16, TIMELINE_RECT.centery), anchor="midleft",
               shadow=False)
        x = TIMELINE_RECT.x + 72
        for i, uid in enumerate(self.timeline[:config.TIMELINE_LENGTH]):
            v = self.views.get(uid)
            if v is None:
                continue
            r = 19 if i == 0 else 15
            cy = TIMELINE_RECT.centery
            ring = "sage_dark" if v.side == "party" else "pink_dark"
            pygame.draw.circle(screen, D.PALETTE[ring], (x, cy), r + 3)
            pygame.draw.circle(screen, D.PALETTE[v.color], (x, cy), r)
            D.text(screen, v.name[0], 15 if i == 0 else 12, "ink", (x, cy), anchor="center", shadow=False)
            x += 66 if i == 0 else 60

    def _draw_leader_panel(self, screen):
        D.panel(screen, LEADER_PANEL, radius=20)
        lv = self.views[self.engine.leader.uid]
        pygame.draw.circle(screen, D.PALETTE[lv.color], (LEADER_PANEL.x + 30, LEADER_PANEL.y + 30), 14)
        D.text(screen, f"{lv.name}  (Leader)", 17, "ink", (LEADER_PANEL.x + 52, LEADER_PANEL.y + 14), shadow=False)
        lv.bar.draw(screen, (LEADER_PANEL.x + 20, LEADER_PANEL.y + 52, 210, 14))
        D.text(screen, f"{round(lv.bar.value)}/{lv.bar.maximum}", 15, "ink",
               (LEADER_PANEL.x + 240, LEADER_PANEL.y + 49), shadow=False)
        if self.guarded:
            sh = pygame.Rect(LEADER_PANEL.right - 44, LEADER_PANEL.y + 10, 30, 30)
            D.draw_round_rect(screen, sh, D.PALETTE["blue"], 10)
            D.text(screen, "G", 16, "white", sh.center, anchor="center", shadow=False)
        D.text(screen, "SP", 13, "ink_soft", (LEADER_PANEL.x + 20, LEADER_PANEL.y + 76), anchor="midleft",
               shadow=False)
        for i in range(self.max_sp):
            cx = LEADER_PANEL.x + 52 + i * 22
            cy = LEADER_PANEL.y + 76
            pygame.draw.circle(screen, D.PALETTE["ink_soft"], (cx, cy), 8)
            pygame.draw.circle(screen, D.PALETTE["gold"] if i < self.sp else D.PALETTE["cream_dark"], (cx, cy), 6)

    def _draw_menu(self, screen):
        member = self._current_member()
        if member is None:
            return
        D.panel(screen, MENU_PANEL, radius=20)
        D.text(screen, f"{member.name}'s turn", 17, "ink",
               (MENU_PANEL.x + 18, MENU_PANEL.y + 12), shadow=False)
        pygame.draw.circle(screen, D.PALETTE[member.color], (MENU_PANEL.right - 26, MENU_PANEL.y + 22), 9)
        rows = self._menu_rows()
        for i, (_, label, enabled, _) in enumerate(rows):
            rect = self._menu_row_rect(i)
            if i == self.menu_index and self.mode == "menu":
                D.draw_round_rect(screen, rect, D.PALETTE["peach"], 12)
            col = "ink" if enabled else "ink_soft"
            D.text(screen, f"{i + 1}", 13, "ink_soft", (rect.x + 10, rect.centery), anchor="midleft", shadow=False)
            D.text(screen, label, 15, col, (rect.x + 30, rect.centery), anchor="midleft", shadow=False)
        if self.mode == "target":
            hint = "Left/Right: target   Enter: confirm   Esc: back"
            col = "ink"
        elif self.reason_timer > 0:
            hint, col = self.reason, "pink_dark"
        else:
            hint, col = rows[self.menu_index][3], ("ink_soft" if rows[self.menu_index][2] else "pink_dark")
        D.text(screen, hint, 12, col, (MENU_PANEL.x + 18, MENU_PANEL.bottom - 18), anchor="midleft", shadow=False)

    def _draw_banner(self, screen):
        if self.banner_timer <= 0:
            return
        p = 1 - self.banner_timer / BANNER_SECONDS
        alpha = int(255 * min(1.0, p * 5, (1 - p) * 4))
        img_w = D.font(22).size(self.banner)[0]
        box = pygame.Rect(0, 0, img_w + 60, 46)
        box.center = (W // 2, 112)
        D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["cream"], int(alpha * 0.92)), 23)
        D.text(screen, self.banner, 22, "ink", box.center, anchor="center", shadow=False, alpha=alpha)

    def _draw_center_banner(self, screen, txt, col):
        p = D.ease_out_cubic(self.mode_age / 0.35)
        box = pygame.Rect(0, 0, int(340 * (0.8 + 0.2 * p)), 90)
        box.center = (W // 2, H // 2 - 30)
        D.panel(screen, box, radius=45)
        D.text(screen, txt, 44, col, box.center, anchor="center")

    def _draw_rewards(self, screen):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill(D.with_alpha(D.PALETTE["ink"], 110))
        screen.blit(veil, (0, 0))
        D.text(screen, "Choose a reward", 34, "cream", (W // 2, H // 2 - CARD_H // 2 - 40), anchor="center")
        heal = round(self.run.leader_max_hp * config.VICTORY_HEAL_PCT)
        D.text(screen, f"Then the leader rests and heals {heal} HP", 15, "cream",
               (W // 2, H // 2 + CARD_H // 2 + 50), anchor="center")
        for i, reward in enumerate(self.rewards):
            rect = self._card_rect(i)
            lift = -8 if i == self.reward_index else 0
            rect = rect.move(0, lift)
            D.panel(screen, rect, radius=22, fill="cream", alpha=245,
                    outline="peach_dark" if i == self.reward_index else "ink_soft")
            if i == self.reward_index:
                D.draw_round_rect(screen, rect, D.PALETTE["peach_dark"], 22, width=4)
            badge = pygame.Rect(rect.x + 14, rect.y + 14, 28, 28)
            D.draw_round_rect(screen, badge, D.PALETTE["peach"], 14)
            D.text(screen, str(i + 1), 15, "ink", badge.center, anchor="center", shadow=False)
            D.text(screen, reward["name"], 18, "ink", (rect.centerx, rect.y + 72), anchor="center", shadow=False)
            D.text(screen, reward["desc"], 14, "ink_soft", (rect.centerx, rect.y + 108), anchor="center",
                   shadow=False)

    def debug_lines(self):
        e = self.engine
        lines = [f"mode {self.mode}  queue {len(self.queue)}  SP {e.sp}/{e.max_sp}  guard_by {e.guard_by}  "
                 f"party actions {e.party_actions}  auto {'on' if self.auto_battle else 'off'}",
                 "gauges: " + "  ".join(f"{u.name}:{u.gauge}/{u.spd}" for u in e.units()),
                 f"buffs: {', '.join(b['name'] for b in self.run.buffs) or 'none'}   ward left {e.ward}"]
        for en in e.enemies:
            intent = en.intent["name"] if en.intent else "-"
            lines.append(f"{en.name}: HP {en.hp}/{en.max_hp} intent {intent} charging {en.charging} "
                         f"phase2 {en.phase2}")
        return lines
