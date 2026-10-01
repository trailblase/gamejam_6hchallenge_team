"""Overworld presentation + input. Rules live in overworld/world.py."""

import math
import random

import pygame

from data import config
from data.characters import CHARACTERS
from data.enemies import ENEMIES, BOSSES
from overworld.world import World
from ui import draw as D
from ui import sprites as S

T = config.TILE
LEADER_W, LEADER_H = 24, 28
FOLLOWER_W, FOLLOWER_H = 21, 25
OVERWORLD_ENEMY_SCALE = 0.55
OVERWORLD_BOSS_SCALE = 0.62
TOAST_SECONDS = 2.2


class OverworldScene:
    def __init__(self, app):
        self.app = app
        self.run = app.run
        self.world = World(app.rng, self.run.defeated, self.run.springs_used, self.run.chests_opened)
        print(f"[overworld] map check ok: {self.world.reachable_tiles} reachable tiles; "
              f"corruption seeds {self.world.corruption.count}, cap {self.world.corruption.cap}")
        self.ground = self._render_ground()
        self.props = self._collect_props()
        self.t = 0.0
        self.hint_timer = config.HINT_SECONDS if app.first_run else 0.0
        app.first_run = False
        self.toast = ""
        self.toast_timer = 0.0
        self.hp_bar = D.AnimatedBar(self.run.leader_hp, self.run.leader_max_hp)
        self.dust = []                  # [x, y, vx, vy, age] in world px
        self.dust_timer = 0.0
        self.fx_rng = random.Random(99)  # visual-only randomness; never touches the game RNG
        self.meter = self.world.corruption.fraction_of_cap
        self.buff_popup = None
        self.buff_timer = 0.0
        self.overlay_cache = {}

    # ------------------------------------------------------------ prerender
    def _render_ground(self):
        tm = self.world.map
        w, h = tm.pixel_size
        surf = pygame.Surface((w, h))
        surf.fill(D.PALETTE["grass"])
        deco = random.Random(1234)     # visual-only noise, separate from the game RNG
        for ty in range(tm.h):
            for tx in range(tm.w):
                x, y = tx * T, ty * T
                if deco.random() < 0.35:
                    pygame.draw.ellipse(surf, D.PALETTE["grass_dark"],
                                        (x + deco.randint(2, 20), y + deco.randint(2, 24), 10, 5))
        for ty in range(tm.h):
            for tx in range(tm.w):
                kind = tm.kind(tx, ty)
                if kind in ("path", "water"):
                    self._rounded_tile(surf, tm, tx, ty, kind,
                                       D.PALETTE["path"] if kind == "path" else D.PALETTE["blue"])
                elif kind == "flowers":
                    for _ in range(3):
                        fx = tx * T + deco.randint(6, T - 6)
                        fy = ty * T + deco.randint(6, T - 6)
                        petal = D.PALETTE[deco.choice(["pink", "peach", "cream", "lavender"])]
                        pygame.draw.circle(surf, petal, (fx, fy), 3)
                        pygame.draw.circle(surf, D.PALETTE["gold"], (fx, fy), 1)
        return surf

    @staticmethod
    def _rounded_tile(surf, tm, tx, ty, kind, col):
        same = lambda dx, dy: tm.kind(tx + dx, ty + dy) == kind  # noqa: E731
        r = T // 2
        radii = {
            "border_top_left_radius": 0 if (same(-1, 0) or same(0, -1)) else r,
            "border_top_right_radius": 0 if (same(1, 0) or same(0, -1)) else r,
            "border_bottom_left_radius": 0 if (same(-1, 0) or same(0, 1)) else r,
            "border_bottom_right_radius": 0 if (same(1, 0) or same(0, 1)) else r,
        }
        pygame.draw.rect(surf, col, (tx * T, ty * T, T, T), border_radius=1, **radii)

    def _collect_props(self):
        props = []
        tm = self.world.map
        for ty in range(tm.h):
            for tx in range(tm.w):
                kind = tm.kind(tx, ty)
                if kind in ("tree", "bush"):
                    props.append((kind, tx * T + T / 2, (ty + 1) * T))
        return props

    # ---------------------------------------------------------------- input
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_e:
            chest = self.world.open_chest()
            if chest:
                self._open_chest(chest)
                return
            spring = self.world.use_spring()
            if spring:
                self.run.springs_used.add(spring.id)
                self.run.full_heal()
                self._toast("The spring restores the leader to full HP!")
                print(f"[overworld] used {spring.id}: leader HP {self.run.leader_hp}/{self.run.leader_max_hp}")
        elif event.key == pygame.K_F2:
            self._debug_win_nearest()
        elif event.key == pygame.K_F4:
            n = self.world.force_spread()
            c = self.world.corruption
            print(f"[debug] F4 spread step: +{n} tiles ({c.count}/{c.cap})")
        elif event.key == pygame.K_F3:
            boss = self.world.teleport_near_next_boss(config.WINDOW_W, config.WINDOW_H)
            print(f"[debug] teleported near {boss.key if boss else 'nothing (no bosses left)'}")

    def _open_chest(self, chest):
        buff = self.run.roll_buff()
        self.run.chests_opened.add(chest.id)
        self.run.apply_buff(buff)
        self.buff_popup = buff
        self.buff_timer = config.BUFF_POPUP_SECONDS
        print(f"[overworld] opened {chest.id}: buff {buff['name']} ({buff['desc']}); "
              f"modifiers {self.run.battle_modifiers()}, buff ATK +{self.run.buff_total('atk_pct'):.0%}, "
              f"leader HP {self.run.leader_hp}/{self.run.leader_max_hp}")

    def _toast(self, msg):
        self.toast = msg
        self.toast_timer = TOAST_SECONDS

    # --------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        touched = self.world.update(dt, mx, my, config.WINDOW_W, config.WINDOW_H)
        if self.hint_timer > 0:
            self.hint_timer -= dt
        if self.toast_timer > 0:
            self.toast_timer -= dt
        self.hp_bar.set(self.run.leader_hp, self.run.leader_max_hp)
        self.hp_bar.update(dt)
        self._update_corruption_fx(dt)
        if touched:
            self._start_battle(touched)

    def _update_corruption_fx(self, dt):
        target = self.world.corruption.fraction_of_cap
        self.meter += (target - self.meter) * min(1.0, config.CORRUPT_METER_LERP * dt)
        if self.buff_timer > 0:
            self.buff_timer -= dt
        p = self.world.player
        if self.world.leader_slowed:
            self.dust_timer -= dt
            if self.dust_timer <= 0:
                self.dust_timer = config.CORRUPT_DUST_INTERVAL * (1 if p.moving else 3)
                r = self.fx_rng
                self.dust.append([p.x + r.uniform(-8, 8), p.y - 2, r.uniform(-14, 14), r.uniform(-26, -10), 0.0])
        for d in self.dust:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[4] += dt
        self.dust = [d for d in self.dust if d[4] < config.CORRUPT_DUST_LIFE]

    def _start_battle(self, enemy):
        from battle.scene import BattleScene
        names = BOSSES[enemy.key]["name"] if enemy.is_boss else " + ".join(enemy.key)
        print(f"[overworld] battle start: {names} ({enemy.id})")
        snapshot = self.app.screen.copy()
        self.app.transition_to(BattleScene(self.app, self, enemy, snapshot))

    def on_battle_end(self, enemy, outcome):
        """Called by the battle scene once its result (and reward) is done."""
        if outcome == "victory":
            self.world.remove_enemy(enemy.id)
            self.run.record_defeat(enemy.id, enemy.key if enemy.is_boss else None)
            if enemy.is_boss:
                self._toast(f"Boss defeated!  {len(self.run.bosses_defeated)}/{config.BOSSES_TO_WIN}")
            if self.run.all_bosses_defeated:
                from scenes.end_screens import WinScene
                self.app.transition_to(WinScene(self.app))
                return
            self.app.transition_to(self)
        elif outcome == "fled":
            self.world.stun_enemy(enemy.id)
            self._toast("You got away! The enemy is dazed for a moment.")
            self.app.transition_to(self)
        else:
            from scenes.end_screens import GameOverScene
            self.app.transition_to(GameOverScene(self.app, self))

    def retry(self):
        self.run.retry()
        self.world.respawn_player(config.WINDOW_W, config.WINDOW_H)
        self.hp_bar = D.AnimatedBar(self.run.leader_hp, self.run.leader_max_hp)
        print("[overworld] retry: respawned at start with full HP")

    def _debug_win_nearest(self):
        enemy = self.world.nearest_enemy()
        if not enemy:
            print("[debug] no enemies left")
            return
        print(f"[debug] instantly won against {enemy.id}")
        self.on_battle_end(enemy, "victory")

    # ----------------------------------------------------------------- draw
    def draw(self, screen):
        cam_x, cam_y = int(self.world.cam_x), int(self.world.cam_y)
        vw, vh = screen.get_size()
        screen.blit(self.ground, (-cam_x, -cam_y))
        self._draw_water_ripples(screen, cam_x, cam_y, vw, vh)
        self._draw_corruption(screen, cam_x, cam_y, vw, vh)

        drawables = []
        margin = T * 2
        for kind, x, y in self.props:
            sx, sy = x - cam_x, y - cam_y
            if -margin < sx < vw + margin and -margin < sy < vh + margin * 2:
                drawables.append((y, kind, sx, sy, None))
        for spring in self.world.springs:
            drawables.append((spring.y, "spring", spring.x - cam_x, spring.y - cam_y, spring))
        for chest in self.world.chests:
            drawables.append((chest.y, "chest", chest.x - cam_x, chest.y - cam_y, chest))
        for enemy in self.world.enemies:
            drawables.append((enemy.y, "enemy", enemy.x - cam_x, enemy.y - cam_y, enemy))
        followers = self.world.follower_positions()
        team = self.run.team
        others = [k for i, k in enumerate(team) if i != self.run.leader_index]
        for key, (fx, fy) in zip(others, followers):
            drawables.append((fy - 0.1, "follower", fx - cam_x, fy - cam_y, key))
        p = self.world.player
        drawables.append((p.y, "leader", p.x - cam_x, p.y - cam_y, None))

        drawables.sort(key=lambda d: d[0])
        for _, kind, sx, sy, obj in drawables:
            if kind == "tree":
                S.draw_tree(screen, sx, sy, T, self.t)
            elif kind == "bush":
                S.draw_bush(screen, sx, sy, T)
            elif kind == "spring":
                S.draw_spring(screen, sx, sy, obj.used, self.t)
            elif kind == "chest":
                S.draw_chest(screen, sx, sy, obj.opened, self.t)
            elif kind == "enemy":
                self._draw_enemy(screen, obj, sx, sy)
            elif kind == "follower":
                bob = math.sin(self.t * 9 + sx * 0.1) * 2 if p.moving else math.sin(self.t * config.BOB_SPEED) * 1.5
                S.draw_body(screen, sx, sy - abs(bob), FOLLOWER_W, FOLLOWER_H, CHARACTERS[obj]["color"],
                            facing_x=p.facing[0])
            elif kind == "leader":
                self._draw_dust(screen, cam_x, cam_y)
                bob = abs(math.sin(self.t * 10)) * 3 if p.moving else math.sin(self.t * config.BOB_SPEED) * 1.5
                S.draw_body(screen, sx, sy - bob, LEADER_W, LEADER_H,
                            CHARACTERS[self.run.leader_key]["color"], facing_x=p.facing[0])
                D.draw_round_rect(screen, (sx - 5, sy - LEADER_H - 14 - bob, 10, 6), D.PALETTE["gold"], 3)

        self._draw_hud(screen)

    def _overlay_tile(self, mask):
        """Purple tile, corners rounded only where no corrupted neighbor
        touches. mask bits: up, right, down, left."""
        surf = self.overlay_cache.get(mask)
        if surf is None:
            r = T // 3
            up, right, down, left = (mask >> 3) & 1, (mask >> 2) & 1, (mask >> 1) & 1, mask & 1
            surf = pygame.Surface((T, T), pygame.SRCALPHA)
            pygame.draw.rect(surf, D.PALETTE["plum"], surf.get_rect(), border_radius=1,
                             border_top_left_radius=0 if (up or left) else r,
                             border_top_right_radius=0 if (up or right) else r,
                             border_bottom_left_radius=0 if (down or left) else r,
                             border_bottom_right_radius=0 if (down or right) else r)
            self.overlay_cache[mask] = surf
        return surf

    def _draw_corruption(self, screen, cam_x, cam_y, vw, vh):
        c = self.world.corruption
        lo, hi = config.CORRUPT_ALPHA
        alpha = int(lo + (hi - lo) * (0.5 + 0.5 * math.sin(self.t * config.CORRUPT_PULSE_SPEED)))
        tx0, ty0 = max(0, cam_x // T), max(0, cam_y // T)
        tx1, ty1 = min(c.w - 1, (cam_x + vw) // T + 1), min(c.h - 1, (cam_y + vh) // T + 1)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                if not c.is_corrupt(tx, ty):
                    continue
                mask = (c.is_corrupt(tx, ty - 1) << 3) | (c.is_corrupt(tx + 1, ty) << 2) | \
                       (c.is_corrupt(tx, ty + 1) << 1) | c.is_corrupt(tx - 1, ty)
                surf = self._overlay_tile(mask)
                surf.set_alpha(alpha)
                screen.blit(surf, (tx * T - cam_x, ty * T - cam_y))
                if (tx * 5 + ty * 3) % 4 == 0:
                    sx = tx * T - cam_x + T / 2 + math.sin(self.t * 1.3 + tx) * 7
                    sy = ty * T - cam_y + T / 2 + math.cos(self.t * 0.9 + ty) * 5
                    pygame.draw.circle(screen, D.PALETTE["plum_light"], (sx, sy), 2)

    def _draw_dust(self, screen, cam_x, cam_y):
        for x, y, _, _, age in self.dust:
            p = age / config.CORRUPT_DUST_LIFE
            col = D.mix(D.PALETTE["plum"], D.PALETTE["plum_light"], p)
            pygame.draw.circle(screen, col, (x - cam_x, y - cam_y), 2 + 3 * (1 - p))

    def _draw_corruption_meter(self, screen):
        vh = screen.get_height()
        rect = pygame.Rect(16, 104, 20, vh - 180)
        D.soft_shadow(screen, rect, 10)
        D.draw_round_rect(screen, rect.inflate(8, 8), D.with_alpha(D.PALETTE["cream"], 220), 14)
        D.draw_round_rect(screen, rect, D.PALETTE["cream_dark"], 10)
        fill_h = int(rect.height * max(0.0, min(1.0, self.meter)))
        if fill_h > 0:
            h = max(fill_h, rect.width)
            fill = pygame.Rect(rect.x, rect.bottom - h, rect.width, h)
            D.draw_round_rect(screen, fill, D.PALETTE["plum"], 10)
            shine = fill.inflate(-12, -10)
            if shine.height > 4:
                D.draw_round_rect(screen, shine, D.with_alpha(D.PALETTE["plum_light"], 150), 4)
        D.draw_round_rect(screen, rect, D.PALETTE["ink_soft"], 10, width=2)
        D.text(screen, "rot", 12, "plum", (rect.centerx, rect.y - 14), anchor="center")
        D.text(screen, f"{round(self.meter * 100)}%", 13, "plum", (rect.centerx, rect.bottom + 16), anchor="center")

    def _draw_water_ripples(self, screen, cam_x, cam_y, vw, vh):
        tm = self.world.map
        tx0, ty0 = max(0, cam_x // T), max(0, cam_y // T)
        tx1, ty1 = min(tm.w - 1, (cam_x + vw) // T + 1), min(tm.h - 1, (cam_y + vh) // T + 1)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                if tm.kind(tx, ty) != "water" or (tx * 7 + ty * 3) % 3:
                    continue
                ox = math.sin(self.t * 1.2 + tx * 0.8 + ty * 0.5) * 6
                rx = tx * T - cam_x + T / 2 + ox - 7
                ry = ty * T - cam_y + T / 2 + math.cos(self.t + tx) * 2
                D.draw_round_rect(screen, (rx, ry, 14, 4), D.PALETTE["blue_light"], 2)

    def _draw_enemy(self, screen, enemy, sx, sy):
        if enemy.is_boss:
            data = BOSSES[enemy.key]
            size = data["size"] * OVERWORLD_BOSS_SCALE
            pulse = 0.5 + 0.5 * math.sin(self.t * 2)
            S.draw_glow(screen, sx, sy - size * 0.5, size * (1.2 + 0.15 * pulse), data["color"], 1.0)
            bob = math.sin(self.t * 1.5) * 2
            S.draw_body(screen, sx, sy - bob, size, size * 0.95, data["color"])
            D.text(screen, data["name"], 14, "ink", (sx, sy - size - 20), anchor="center")
            return
        data = ENEMIES[enemy.key[0]]
        size = data["size"] * OVERWORLD_ENEMY_SCALE
        stunned = enemy.stun > 0
        alpha = 150 if stunned and int(self.t * 8) % 2 else 255
        hop = abs(math.sin(self.t * 8)) * 3 if enemy.chasing else math.sin(self.t * 2 + enemy.home[0]) * 1.5
        S.draw_body(screen, sx, sy - hop, size, size * 0.85, data["color"], alpha=alpha,
                    facing_x=0.6 if self.world.player.x > enemy.x else -0.6)
        if len(enemy.key) > 1:
            pill = pygame.Rect(0, 0, 26, 16)
            pill.center = (sx + size * 0.55, sy - size * 0.9)
            D.draw_round_rect(screen, pill, D.PALETTE["cream"], 8)
            D.text(screen, f"x{len(enemy.key)}", 11, "ink", pill.center, anchor="center", shadow=False)
        if stunned:
            D.text(screen, "zz", 13, "ink_soft", (sx, sy - size - 10), anchor="center", shadow=False)
        elif enemy.chasing:
            D.text(screen, "!", 18, "pink_dark", (sx, sy - size - 12), anchor="center")

    def _draw_hud(self, screen):
        vw, vh = screen.get_size()
        D.panel(screen, (14, 12, 250, 58), radius=18)
        leader = CHARACTERS[self.run.leader_key]
        pygame.draw.circle(screen, D.PALETTE[leader["color"]], (36, 41), 11)
        D.text(screen, f"{leader['name']}  (Leader)", 15, "ink", (54, 18), shadow=False)
        self.hp_bar.draw(screen, (54, 42, 150, 12))
        D.text(screen, f"{self.run.leader_hp}/{self.run.leader_max_hp}", 13, "ink", (210, 38), shadow=False)

        boss_txt = f"Bosses {len(self.run.bosses_defeated)}/{config.BOSSES_TO_WIN}"
        pill = pygame.Rect(0, 0, 130, 36)
        pill.topright = (vw - 14, 14)
        D.panel(screen, pill, radius=18)
        D.text(screen, boss_txt, 16, "ink", pill.center, anchor="center", shadow=False)

        self._draw_corruption_meter(screen)
        chest = self.world.nearby_chest()
        if chest:
            tip = pygame.Rect(0, 0, 120, 28)
            tip.midbottom = (chest.x - self.world.cam_x, chest.y - self.world.cam_y - 34)
            D.panel(screen, tip, radius=14)
            D.text(screen, "E  Open", 14, "ink", tip.center, anchor="center", shadow=False)
        spring = None if chest else self.world.nearby_spring()
        if spring:
            sx = spring.x - self.world.cam_x
            sy = spring.y - self.world.cam_y
            tip = pygame.Rect(0, 0, 130, 28)
            tip.midbottom = (sx, sy - 34)
            D.panel(screen, tip, radius=14)
            D.text(screen, "E  Drink", 14, "ink", tip.center, anchor="center", shadow=False)

        if self.hint_timer > 0:
            a = int(255 * min(1.0, self.hint_timer))
            box = pygame.Rect(0, 0, 640, 36)
            box.midbottom = (vw / 2, vh - 16)
            D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["cream"], int(a * 0.85)), 18)
            D.text(screen, "WASD / Arrows: move     E: open chest / drink     F1: debug", 15, "ink",
                   box.center, anchor="center", shadow=False, alpha=a)

        if self.buff_popup and self.buff_timer > 0:
            age = config.BUFF_POPUP_SECONDS - self.buff_timer
            a = int(255 * min(1.0, age / 0.25, self.buff_timer / 0.4))
            rise = (1 - D.ease_out_cubic(age / 0.4)) * 16
            box = pygame.Rect(0, 0, 340, 70)
            box.midtop = (vw / 2, 112 + rise)
            D.draw_round_rect(screen, box.move(0, 5), D.with_alpha(D.PALETTE["ink"], int(a * 0.25)), 24)
            D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["cream"], int(a * 0.95)), 24)
            D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["gold"], a), 24, width=3)
            D.text(screen, f"Buff: {self.buff_popup['name']}", 22, "ink", (box.centerx, box.y + 22),
                   anchor="center", shadow=False, alpha=a)
            D.text(screen, self.buff_popup["desc"], 14, "ink_soft", (box.centerx, box.y + 50),
                   anchor="center", shadow=False, alpha=a)

        if self.toast_timer > 0:
            a = int(255 * min(1.0, self.toast_timer / 0.4))
            box = pygame.Rect(0, 0, 470, 36)
            box.midtop = (vw / 2, 70)
            D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["cream"], int(a * 0.9)), 18)
            D.text(screen, self.toast, 15, "ink", box.center, anchor="center", shadow=False, alpha=a)

    def debug_lines(self):
        p = self.world.player
        near = self.world.nearest_enemy()
        lines = [f"player feet ({p.x:.0f},{p.y:.0f}) tile ({int(p.x // T)},{int(p.y // T)})",
                 f"enemies left {len(self.world.enemies)}  bosses {sorted(self.run.bosses_defeated)}",
                 f"leader HP {self.run.leader_hp}/{self.run.leader_max_hp}  "
                 f"atk+{self.run.atk_pct:.0%} spd+{self.run.spd_bonus} maxSP {self.run.max_sp}"]
        c = self.world.corruption
        lines.append(f"corrupted tiles {c.count}/{c.cap} (cap {config.CORRUPT_MAX_FRACTION:.0%} of {c.walkable} "
                     f"walkable)  next spread {config.CORRUPT_SPREAD_INTERVAL - self.world.spread_timer:.1f}s  "
                     f"slowed {self.world.leader_slowed}")
        buffs = ", ".join(b["name"] for b in self.run.buffs) or "none"
        lines.append(f"buffs: {buffs}   battle modifiers {self.run.battle_modifiers()}")
        if near:
            d = math.hypot(near.x - p.x, near.y - p.y)
            lines.append(f"nearest {near.id} dist {d:.0f} stun {near.stun:.1f} chasing {near.chasing}")
        return lines
