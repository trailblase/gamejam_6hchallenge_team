"""Overworld presentation + input. Rules live in overworld/world.py."""

import math
import random

import pygame

from data import config
from data.characters import CHARACTERS
from data.enemies import ENEMIES, BOSSES
from overworld.world import World
from ui import audio
from ui import draw as D
from ui import sprites as S
from ui.character_sprites import draw_character
from ui import topdown_assets as TD
from ui.weather import draw_corruption_weather

T = config.TILE
LEADER_W, LEADER_H = 24, 28
FOLLOWER_W, FOLLOWER_H = 21, 25
OVERWORLD_ENEMY_SCALE = 0.55
OVERWORLD_BOSS_SCALE = 0.62
TOAST_SECONDS = 2.2
MINIMAP_SCALE = 3          # pixels per tile on the corner map
MINIMAP_PAD = 8
MINIMAP_MARGIN = 14

# Short enough that letting every bubble play out stays under about 20 seconds.
# Space finishes the current bubble, then advances.
GUIDE_SCRIPT = [
    ["I'm Suspicious Mustache.",
     "This was a peaceful world of slimes."],
    ["The corruption must be cleansed.",
     "Defeat the three bosses on the map."],
    ["The purple meter is how much has spread.",
     "More tiles rot as time goes on."],
    ["Purple ground slows you down",
     "and drains your HP, slowly."],
    ["Step into their area and small enemies",
     "pull you into a fight."],
    ["Attack, Skill, Block, or Flee.",
     "The leader's HP is the whole team's."],
    ["A win pauses the rot. Here's a buff.",
     "Chests give more. Springs restore HP."],
]


class _Talk:
    def __init__(self):
        self.index = 0
        self.shown = 0.0
        self.hold = 0.0

    def lines(self):
        return GUIDE_SCRIPT[self.index]

    def length(self):
        return sum(len(line) for line in self.lines())

    def complete(self):
        return self.shown >= self.length()

    def visible(self):
        left = int(self.shown)
        out = []
        for line in self.lines():
            if left <= 0:
                break
            out.append(line[:left])
            left -= len(line)
        return out


class OverworldScene:
    def __init__(self, app):
        self.app = app
        self.medieval_mode = app.medieval_mode
        self.run = app.run
        self.world = World(app.rng, self.run.defeated, self.run.springs_used, self.run.chests_opened)
        print(f"[overworld] map check ok: {self.world.reachable_tiles} reachable tiles; "
              f"corruption seeds {self.world.corruption.count}, cap {self.world.corruption.cap}")
        audio.play_music("overworld")
        self.ground = self._render_ground()
        self.minimap = self._render_minimap()
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
        self.corruption_damage_fraction = 0.0
        self._was_on_corruption = False
        self.talk = None
        self.guide_gifted = False

    # ------------------------------------------------------------ prerender
    def _render_ground(self):
        tm = self.world.map
        w, h = tm.pixel_size
        if self.medieval_mode:
            surf = pygame.Surface((w, h))
            for ty in range(tm.h):
                for tx in range(tm.w):
                    surf.blit(TD.ground_tile(tm.kind(tx, ty), tx, ty), (tx * T, ty * T))
            return surf
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

    def _render_minimap(self):
        tm = self.world.map
        scale = MINIMAP_SCALE
        colors = {
            "grass": D.PALETTE["grass"],
            "flowers": D.PALETTE["sage_light"],
            "path": D.PALETTE["path"],
            "water": D.PALETTE["blue"],
            "tree": D.PALETTE["sage_dark"],
            "bush": D.PALETTE["sage"],
        }
        surf = pygame.Surface((tm.w * scale, tm.h * scale))
        for ty in range(tm.h):
            for tx in range(tm.w):
                surf.fill(colors.get(tm.kind(tx, ty), D.PALETTE["grass"]),
                          (tx * scale, ty * scale, scale, scale))
        return surf

    def _minimap_panel(self, vw, vh):
        tm = self.world.map
        rect = pygame.Rect(0, 0, tm.w * MINIMAP_SCALE + MINIMAP_PAD * 2,
                           tm.h * MINIMAP_SCALE + MINIMAP_PAD * 2 + 14)
        rect.bottomright = (vw - MINIMAP_MARGIN, vh - MINIMAP_MARGIN)
        return rect

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
                    variant = (tx * 7 + ty * 11) % (3 if kind == "tree" else 6)
                    props.append((kind, tx * T + T / 2, (ty + 1) * T, variant))
        return props

    # ---------------------------------------------------------------- input
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE and self.talk:
            self._skip_talk()
            return
        if event.key == pygame.K_F2:
            self._debug_win_nearest()
        elif event.key == pygame.K_F4:
            n = self.world.force_spread()
            c = self.world.corruption
            print(f"[debug] F4 spread step: +{n} tiles ({c.count}/{c.cap})")
        elif event.key == pygame.K_F3:
            boss = self.world.teleport_near_next_boss(config.WINDOW_W, config.WINDOW_H)
            print(f"[debug] teleported near {boss.key if boss else 'nothing (no bosses left)'}")
        elif self.talk:
            return
        elif event.key == pygame.K_e:
            if self.world.nearby_guide():
                self.talk = _Talk()
                print("[overworld] Suspicious Mustache starts talking")
                return
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

    def _skip_talk(self):
        """Space finishes the current bubble, then moves to the next."""
        talk = self.talk
        if not talk.complete():
            talk.shown = talk.length()
            if talk.index == len(GUIDE_SCRIPT) - 1:
                self._gift_buff()
            return
        self._advance_talk()

    def _advance_talk(self):
        self.talk.index += 1
        if self.talk.index >= len(GUIDE_SCRIPT):
            self.talk = None
            return
        self.talk.shown = 0.0
        self.talk.hold = 0.0

    def _gift_buff(self):
        if self.guide_gifted:
            return
        self.guide_gifted = True
        buff = self.run.roll_buff()
        self.run.apply_buff(buff)
        self.buff_popup = buff
        self.buff_timer = config.BUFF_POPUP_SECONDS
        print(f"[overworld] Suspicious Mustache gave buff {buff['name']} ({buff['desc']})")

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
        if self.talk:
            mx = my = 0
        else:
            mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        touched = self.world.update(dt, mx, my, config.WINDOW_W, config.WINDOW_H,
                                     freeze_enemies=self.talk is not None)
        on_corruption = self.world.leader_slowed
        if on_corruption:
            if not self._was_on_corruption:
                self.run.touch_corruption()
                self._toast("Rot burns you. Party ATK -10% next battle.")
            self.corruption_damage_fraction += dt * config.CORRUPTION_TILE_DPS
            damage = int(self.corruption_damage_fraction)
            if damage:
                self.corruption_damage_fraction -= damage
                self.run.damage_leader(damage)
        self._was_on_corruption = on_corruption
        if self.hint_timer > 0:
            self.hint_timer -= dt
        if self.toast_timer > 0:
            self.toast_timer -= dt
        self._update_talk(dt)
        self.hp_bar.set(self.run.leader_hp, self.run.leader_max_hp)
        self.hp_bar.update(dt)
        self._update_corruption_fx(dt)
        if self.run.leader_hp <= 0:
            from scenes.end_screens import GameOverScene
            self.app.transition_to(GameOverScene(self.app, self))
            return
        if touched and not self.talk:
            self._start_battle(touched)

    def _update_talk(self, dt):
        talk = self.talk
        if not talk:
            return
        if not talk.complete():
            talk.shown = min(talk.length(), talk.shown + config.GUIDE_CHARS_PER_SEC * dt)
            if talk.complete() and talk.index == len(GUIDE_SCRIPT) - 1:
                self._gift_buff()
            return
        talk.hold += dt
        if talk.hold >= config.GUIDE_LINE_HOLD:
            self._advance_talk()

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
            self.world.pause_spread(config.CORRUPT_PAUSE_ON_WIN)
            self.run.record_defeat(enemy.id, enemy.key if enemy.is_boss else None)
            if enemy.is_boss:
                self._toast(f"Boss defeated!  {len(self.run.bosses_defeated)}/{config.BOSSES_TO_WIN}")
            if self.run.all_bosses_defeated:
                from scenes.end_screens import WinScene
                self.app.transition_to(WinScene(self.app))
                return
            audio.play_music("overworld")
            self.app.transition_to(self)
        elif outcome == "fled":
            self.world.stun_enemy(enemy.id)
            self._toast("You got away! The enemy is dazed for a moment.")
            audio.play_music("overworld")
            self.app.transition_to(self)
        else:
            from scenes.end_screens import GameOverScene
            self.app.transition_to(GameOverScene(self.app, self))

    def retry(self):
        self.talk = None
        self.run.retry()
        self.world.respawn_player(config.WINDOW_W, config.WINDOW_H)
        self.hp_bar = D.AnimatedBar(self.run.leader_hp, self.run.leader_max_hp)
        audio.play_music("overworld")
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
        for kind, x, y, variant in self.props:
            sx, sy = x - cam_x, y - cam_y
            if -margin < sx < vw + margin and -margin < sy < vh + margin * 2:
                drawables.append((y, kind, sx, sy, variant))
        for spring in self.world.springs:
            drawables.append((spring.y, "spring", spring.x - cam_x, spring.y - cam_y, spring))
        for chest in self.world.chests:
            drawables.append((chest.y, "chest", chest.x - cam_x, chest.y - cam_y, chest))
        for enemy in self.world.enemies:
            drawables.append((enemy.y, "enemy", enemy.x - cam_x, enemy.y - cam_y, enemy))
        if self.world.guide:
            guide = self.world.guide
            drawables.append((guide.y, "guide", guide.x - cam_x, guide.y - cam_y, guide))
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
                if self.medieval_mode:
                    TD.draw_tree(screen, sx, sy, obj)
                else:
                    S.draw_tree(screen, sx, sy, T, self.t)
            elif kind == "bush":
                if self.medieval_mode:
                    TD.draw_bush(screen, sx, sy, obj)
                else:
                    S.draw_bush(screen, sx, sy, T)
            elif kind == "spring":
                if self.medieval_mode:
                    TD.draw_spring(screen, sx, sy, obj.used)
                else:
                    S.draw_spring(screen, sx, sy, obj.used, self.t)
            elif kind == "chest":
                if self.medieval_mode:
                    TD.draw_chest(screen, sx, sy, obj.opened)
                else:
                    S.draw_chest(screen, sx, sy, obj.opened, self.t)
            elif kind == "enemy":
                self._draw_enemy(screen, obj, sx, sy)
            elif kind == "guide":
                facing = -0.6 if p.x < obj.x else 0.6
                S.draw_guide(screen, sx, sy, self.t, facing)
                if not self.talk:
                    D.text(screen, obj.name, 13, "ink", (sx, sy - 56), anchor="center")
            elif kind == "follower":
                if self.medieval_mode:
                    TD.draw_player(screen, sx, sy, p.facing, D.PALETTE[CHARACTERS[obj]["color"]],
                                   self.t + sx * 0.013, p.moving)
                else:
                    bob = math.sin(self.t * 9 + sx * 0.1) * 2 if p.moving else math.sin(self.t * config.BOB_SPEED) * 1.5
                    S.draw_body(screen, sx, sy - abs(bob), FOLLOWER_W, FOLLOWER_H, CHARACTERS[obj]["color"],
                                facing_x=p.facing[0])
            elif kind == "leader":
                self._draw_dust(screen, cam_x, cam_y)
                if self.medieval_mode:
                    TD.draw_player(screen, sx, sy, p.facing,
                                   D.PALETTE[CHARACTERS[self.run.leader_key]["color"]], self.t, p.moving)
                    D.draw_round_rect(screen, (sx - 5, sy - 46, 10, 6), D.PALETTE["gold"], 3)
                else:
                    bob = abs(math.sin(self.t * 10)) * 3 if p.moving else math.sin(self.t * config.BOB_SPEED) * 1.5
                    S.draw_body(screen, sx, sy - bob, LEADER_W, LEADER_H,
                                CHARACTERS[self.run.leader_key]["color"], facing_x=p.facing[0])
                    D.draw_round_rect(screen, (sx - 5, sy - LEADER_H - 14 - bob, 10, 6), D.PALETTE["gold"], 3)

        draw_corruption_weather(screen, self.meter, self.t)
        self._draw_hud(screen)
        self._draw_minimap(screen)
        self._draw_talk(screen)

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
        if self.medieval_mode:
            if enemy.is_boss:
                data = BOSSES[enemy.key]
                size = data["size"] * OVERWORLD_BOSS_SCALE
                pulse = 0.5 + 0.5 * math.sin(self.t * 2)
                S.draw_glow(screen, sx, sy - size * 0.5, size * (1.2 + 0.15 * pulse), data["color"], 1.0)
                draw_character(screen, "orc", "idle", self.t, sx, sy, size * 1.35,
                               tint=D.PALETTE[data["color"]])
                D.text(screen, data["name"], 14, "ink", (sx, sy - size - 20), anchor="center")
                return
            data = ENEMIES[enemy.key[0]]
            size = data["size"] * OVERWORLD_ENEMY_SCALE
            stunned = enemy.stun > 0
            alpha = 150 if stunned and int(self.t * 8) % 2 else 255
            walking = enemy.chasing
            bob = abs(math.sin(self.t * 8)) * 3 if walking else math.sin(self.t * 2 + enemy.home[0]) * 1.5
            draw_character(screen, "orc", "walk" if walking else "idle", self.t,
                           sx, sy - bob, size * 1.45,
                           flip=self.world.player.x > enemy.x, alpha=alpha,
                           tint=D.PALETTE[data["color"]])
            if len(enemy.key) > 1:
                pill = pygame.Rect(0, 0, 26, 16)
                pill.center = (sx + size * 0.55, sy - size * 0.9)
                D.draw_round_rect(screen, pill, D.PALETTE["cream"], 8)
                D.text(screen, f"x{len(enemy.key)}", 11, "ink", pill.center, anchor="center", shadow=False)
            if stunned:
                D.text(screen, "zz", 13, "ink_soft", (sx, sy - size - 10), anchor="center", shadow=False)
            elif enemy.chasing:
                D.text(screen, "!", 18, "pink_dark", (sx, sy - size - 12), anchor="center")
            return

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
        if self.run.touched_corruption:
            status = pygame.Rect(0, 0, 218, 26)
            status.topleft = (42, 76)
            D.panel(screen, status, radius=13, fill="cream", alpha=235, outline="plum")
            D.text(screen, "TOUCHED CORRUPTION  ·  ATK -10%", 11, "plum",
                   status.center, anchor="center", shadow=False)

        boss_txt = f"Bosses {len(self.run.bosses_defeated)}/{config.BOSSES_TO_WIN}"
        pill = pygame.Rect(0, 0, 130, 36)
        pill.topright = (vw - 14, 14)
        D.panel(screen, pill, radius=18)
        D.text(screen, boss_txt, 16, "ink", pill.center, anchor="center", shadow=False)

        theme = pygame.Rect(0, 0, 150, 28)
        theme.topright = (vw - 14, 58)
        D.panel(screen, theme, radius=14, fill="cream", alpha=235, outline="gold")
        theme_label = "M  MEDIEVAL" if self.medieval_mode else "M  CLASSIC"
        D.text(screen, theme_label, 12, "ink", theme.center, anchor="center", shadow=False)

        self._draw_corruption_meter(screen)
        guide = None if self.talk else self.world.nearby_guide()
        if guide:
            tip = pygame.Rect(0, 0, 110, 28)
            tip.midbottom = (guide.x - self.world.cam_x, guide.y - self.world.cam_y - 78)
            D.panel(screen, tip, radius=14)
            D.text(screen, "E  Talk", 14, "ink", tip.center, anchor="center", shadow=False)
        chest = None if guide else self.world.nearby_chest()
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

        if self.hint_timer > 0 and not self.talk:
            a = int(255 * min(1.0, self.hint_timer))
            panel = self._minimap_panel(vw, vh)
            box = pygame.Rect(0, 0, 520, 36)
            box.midbottom = ((16 + panel.left - 12) / 2, vh - 16)
            D.draw_round_rect(screen, box, D.with_alpha(D.PALETTE["cream"], int(a * 0.85)), 18)
            D.text(screen, "WASD / Arrows: move     E: talk / chest / spring     F1: debug", 15, "ink",
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

    def _draw_talk(self, screen):
        talk = self.talk
        guide = self.world.guide
        if not talk or not guide:
            return
        lines = talk.lines()
        shown = talk.visible()
        size, name_size, line_h, pad = 16, 14, 22, 16
        text_w = max(D.font(size).size(line)[0] for line in lines)
        text_w = max(text_w, D.font(name_size).size(guide.name)[0])
        box = pygame.Rect(0, 0, text_w + pad * 2, pad + 22 + line_h * len(lines) + 16)
        sx = guide.x - self.world.cam_x
        sy = guide.y - self.world.cam_y - 64
        box.midbottom = (sx, sy)
        vw, vh = screen.get_size()
        box.clamp_ip(pygame.Rect(12, 12, vw - 24, vh - 24))
        mini = self._minimap_panel(vw, vh)
        if box.colliderect(mini):
            box.right = mini.left - 8
        D.panel(screen, box, radius=18)
        D.text(screen, guide.name, name_size, "sage_dark", (box.x + pad, box.y + 10), shadow=False)
        for i, _line in enumerate(lines):
            text = shown[i] if i < len(shown) else ""
            if text:
                D.text(screen, text, size, "ink", (box.x + pad, box.y + 32 + i * line_h), shadow=False)
        prompt = "Space"
        alpha = 255 if talk.complete() else 120
        if talk.complete():
            alpha = int(150 + 105 * (0.5 + 0.5 * math.sin(self.t * 6)))
        D.text(screen, prompt, 12, "ink_soft", (box.right - pad, box.bottom - 8),
               anchor="bottomright", shadow=False, alpha=alpha)

    def _draw_minimap(self, screen):
        """Corner map: terrain, you, and the places worth walking to."""
        vw, vh = screen.get_size()
        panel = self._minimap_panel(vw, vh)
        D.panel(screen, panel, radius=16)
        D.text(screen, "Map", 12, "ink_soft", (panel.x + 12, panel.y + 5), shadow=False)

        scale = MINIMAP_SCALE
        origin = (panel.x + MINIMAP_PAD, panel.y + MINIMAP_PAD + 14)
        tm = self.world.map
        map_rect = pygame.Rect(origin, (tm.w * scale, tm.h * scale))
        screen.blit(self.minimap, origin)

        clip = screen.get_clip()
        screen.set_clip(map_rect)
        corruption = self.world.corruption
        for ty, row in enumerate(corruption.grid):
            for tx, corrupt in enumerate(row):
                if corrupt:
                    screen.fill(D.PALETTE["plum"], (origin[0] + tx * scale, origin[1] + ty * scale, scale, scale))

        view = pygame.Rect(origin[0] + self.world.cam_x / T * scale,
                           origin[1] + self.world.cam_y / T * scale,
                           vw / T * scale, vh / T * scale)
        pygame.draw.rect(screen, D.PALETTE["cream"], view, 1)

        def pin(world_x, world_y):
            return origin[0] + world_x / T * scale, origin[1] + world_y / T * scale

        for chest in self.world.chests:
            if not chest.opened:
                cx, cy = pin(chest.x, chest.y)
                pygame.draw.rect(screen, D.PALETTE["gold"], (cx - 2, cy - 2, 4, 4))
                pygame.draw.rect(screen, D.PALETTE["ink"], (cx - 2, cy - 2, 4, 4), 1)
        for spring in self.world.springs:
            if not spring.used:
                pygame.draw.circle(screen, D.PALETTE["blue_dark"], pin(spring.x, spring.y), 2)

        for enemy in self.world.enemies:
            if not enemy.is_boss:
                continue
            bx, by = pin(enemy.x, enemy.y)
            color = D.PALETTE[BOSSES[enemy.key]["color"]]
            diamond = [(bx, by - 5), (bx + 5, by), (bx, by + 5), (bx - 5, by)]
            pygame.draw.polygon(screen, D.PALETTE["cream"], diamond)
            inner = [(bx, by - 3), (bx + 3, by), (bx, by + 3), (bx - 3, by)]
            pygame.draw.polygon(screen, color, inner)
            pygame.draw.polygon(screen, D.PALETTE["ink"], diamond, 1)

        p = self.world.player
        px, py = pin(p.x, p.y)
        fx, fy = p.facing
        pygame.draw.line(screen, D.PALETTE["ink"], (px, py), (px + fx * 8, py + fy * 8), 2)
        pulse = 3 if int(self.t * 2) % 2 else 4
        pygame.draw.circle(screen, D.PALETTE["white"], (px, py), pulse + 1)
        pygame.draw.circle(screen, D.PALETTE["gold"], (px, py), pulse)
        pygame.draw.circle(screen, D.PALETTE["ink"], (px, py), pulse, 1)
        screen.set_clip(clip)

    def debug_lines(self):
        p = self.world.player
        near = self.world.nearest_enemy()
        lines = [f"player feet ({p.x:.0f},{p.y:.0f}) tile ({int(p.x // T)},{int(p.y // T)})",
                 f"enemies left {len(self.world.enemies)}  bosses {sorted(self.run.bosses_defeated)}",
                 f"leader HP {self.run.leader_hp}/{self.run.leader_max_hp}  "
                 f"atk+{self.run.atk_pct:.0%} spd+{self.run.spd_bonus} maxSP {self.run.max_sp}"]
        c = self.world.corruption
        if self.world.spread_pause > 0:
            spread = f"spread paused {self.world.spread_pause:.1f}s"
        else:
            spread = f"next spread {config.CORRUPT_SPREAD_INTERVAL - self.world.spread_timer:.1f}s"
        lines.append(f"corrupted tiles {c.count}/{c.cap} (cap {config.CORRUPT_MAX_FRACTION:.0%} of {c.walkable} "
                     f"walkable)  {spread}  slowed {self.world.leader_slowed}")
        buffs = ", ".join(b["name"] for b in self.run.buffs) or "none"
        lines.append(f"buffs: {buffs}   battle modifiers {self.run.battle_modifiers()}")
        if near:
            d = math.hypot(near.x - p.x, near.y - p.y)
            lines.append(f"nearest {near.id} dist {d:.0f} stun {near.stun:.1f} chasing {near.chasing}")
        return lines
