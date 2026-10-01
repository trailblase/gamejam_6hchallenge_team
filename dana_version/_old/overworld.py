import math
import random
import pygame
import pixel_font as pf
import ui
from settings import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TILE, SKY_TOP, SKY_BOTTOM, GROUND, GROUND_TOP,
    CORRUPT_TILE, CORRUPT_TILE_PULSE, WHITE, PARTY_COLORS, ENEMY_COLOR,
    ENEMY_BOSS_COLOR, RESTORE_COLOR, PORTAL_COLOR_A, PORTAL_COLOR_B,
    PORTAL_LOCKED_COLOR, DOUBLE_JUMP_MULT, clamp
)
from levels import Level, ROWS

GRAVITY = 1900.0
JUMP_V = -650.0
MOVE_ACCEL = 2400.0
MOVE_SPEED = 260.0
FRICTION = 2000.0
PLAYER_W, PLAYER_H = 28, 40


class Particle:
    def __init__(self, x, y, vx, vy, color, life):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.color = color
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 400 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surface, cam_x):
        a = max(0, self.life / self.max_life)
        size = max(1, int(4 * a))
        pygame.draw.rect(surface, self.color, (self.x - cam_x, self.y, size, size))


class OverworldScene:
    def __init__(self, app):
        self.app = app
        self.data = app.data
        self.level = Level(self.data.level_index)
        sx, sy = self.level.player_start
        self.px = sx * TILE
        self.py = sy * TILE
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.jump_count = 0
        self.jump_key_prev = False
        self.facing = 1
        self.cam_x = 0.0
        self.t = 0.0
        self.particles = []
        self.message = ""
        self.message_timer = 0.0
        self.drain_accum = 0.0
        self.leader_color = PARTY_COLORS.get(
            self.data.party.captain.class_name, (200, 200, 200)
        ) if self.data.party else (200, 200, 200)

    # ---------------- events ----------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()

    # ---------------- update ----------------
    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        status = self.data.status
        speed_mult = status.speed_mult
        jump_mult = status.jump_mult

        move_dir = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move_dir -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move_dir += 1

        target_speed = move_dir * MOVE_SPEED * speed_mult
        if move_dir != 0:
            self.facing = move_dir
            if self.vx < target_speed:
                self.vx = min(target_speed, self.vx + MOVE_ACCEL * dt)
            else:
                self.vx = max(target_speed, self.vx - MOVE_ACCEL * dt)
        else:
            if self.vx > 0:
                self.vx = max(0, self.vx - FRICTION * dt)
            elif self.vx < 0:
                self.vx = min(0, self.vx + FRICTION * dt)

        jump_held = keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]
        jump_edge = jump_held and not self.jump_key_prev
        self.jump_key_prev = jump_held
        if jump_edge:
            if self.on_ground:
                self.vy = JUMP_V * jump_mult
                self.on_ground = False
                self.jump_count = 1
                self._spawn_jump_dust()
            elif self.jump_count == 1:
                self.vy = JUMP_V * DOUBLE_JUMP_MULT * jump_mult
                self.jump_count = 2
                self._spawn_jump_dust()

        self.vy += GRAVITY * dt
        self.vy = min(self.vy, 1400)

        self._move_and_collide(dt)

        # corruption contact + status
        touching_corrupt = self._touching_corrupt_tile()
        if touching_corrupt:
            status.apply_corruption_touch()
            self.data.corruption.add(2.2 * dt)
            if self.t % 1 < 0.1:
                self.particles.append(Particle(
                    self.px + PLAYER_W / 2, self.py + PLAYER_H,
                    (random.random() - 0.5) * 40, -60, CORRUPT_TILE_PULSE, 0.5
                ))

        def drain_tick(dtt):
            self.data.corruption.add(0.6 * dtt)
            # Flat 2 HP/sec, accumulated so short frames don't round up to
            # a forced minimum of 1 HP lost every single frame.
            self.drain_accum += 2.0 * dtt
            if self.drain_accum >= 1.0:
                amount = int(self.drain_accum)
                self.drain_accum -= amount
                for m in self.data.party.alive_members():
                    m.hp = max(1, m.hp - amount)

        status.update(dt, on_drain_tick=drain_tick)

        # ambient corruption creep - the threat approaches even if you
        # never touch a bad tile; fighting monsters is what pushes it back
        self.data.corruption.add(0.35 * dt)

        self.particles = [p for p in self.particles if p.update(dt)]

        # camera
        level_px_w = self.level.pixel_width(TILE)
        target_cam = self.px - WINDOW_WIDTH / 2
        self.cam_x = clamp(target_cam, 0, max(0, level_px_w - WINDOW_WIDTH))

        if self.message_timer > 0:
            self.message_timer -= dt

        self._check_triggers()

        if self.py > ROWS * TILE + 200:
            self._respawn()

    def _spawn_jump_dust(self):
        for _ in range(6):
            self.particles.append(Particle(
                self.px + PLAYER_W / 2, self.py + PLAYER_H,
                (random.random() - 0.5) * 120, -random.random() * 60,
                (210, 200, 220), 0.35
            ))

    def _respawn(self):
        sx, sy = self.level.player_start
        self.px = sx * TILE
        self.py = sy * TILE
        self.vx = 0
        self.vy = 0

    def _move_and_collide(self, dt):
        self.px += self.vx * dt
        self._resolve_collisions(axis='x')
        self.py += self.vy * dt
        self.on_ground = False
        self._resolve_collisions(axis='y')
        if self.on_ground:
            self.jump_count = 0

    def _player_rect(self):
        return pygame.Rect(int(self.px), int(self.py), PLAYER_W, PLAYER_H)

    def _resolve_collisions(self, axis):
        rect = self._player_rect()
        c0 = max(0, rect.left // TILE - 1)
        c1 = min(self.level.cols - 1, rect.right // TILE + 1)
        r0 = max(0, rect.top // TILE - 1)
        r1 = min(ROWS - 1, rect.bottom // TILE + 1)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if not self.level.is_solid(col, row):
                    continue
                tile_rect = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
                if not rect.colliderect(tile_rect):
                    continue
                if axis == 'x':
                    if self.vx > 0:
                        self.px = tile_rect.left - PLAYER_W
                    elif self.vx < 0:
                        self.px = tile_rect.right
                    self.vx = 0
                else:
                    if self.vy > 0:
                        self.py = tile_rect.top - PLAYER_H
                        self.on_ground = True
                    elif self.vy < 0:
                        self.py = tile_rect.bottom
                    self.vy = 0
                rect = self._player_rect()

    def _touching_corrupt_tile(self):
        rect = self._player_rect()
        rect.y += 2
        c0 = max(0, rect.left // TILE)
        c1 = min(self.level.cols - 1, rect.right // TILE)
        r0 = max(0, rect.top // TILE)
        r1 = min(ROWS - 1, rect.bottom // TILE)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if self.level.is_corrupt(col, row):
                    tile_rect = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
                    if rect.colliderect(tile_rect):
                        return True
        return False

    def _check_triggers(self):
        rect = self._player_rect()

        for trig in list(self.level.normal_triggers):
            tc, tr = trig
            trect = pygame.Rect(tc * TILE, tr * TILE, TILE, TILE)
            if rect.colliderect(trect):
                self.level.normal_triggers.remove(trig)
                self._start_battle(kind="normal")
                return

        if not self.level.boss_defeated and self.level.boss_trigger:
            tc, tr = self.level.boss_trigger
            trect = pygame.Rect(tc * TILE, tr * TILE, TILE, TILE)
            if rect.colliderect(trect):
                self._start_battle(kind=self.level.boss_kind, is_level_boss=True)
                return

        for rp in self.level.restore_points:
            rc, rr, used = rp
            if used:
                continue
            rrect = pygame.Rect(rc * TILE, rr * TILE, TILE, TILE)
            if rect.colliderect(rrect):
                rp[2] = True
                self.data.party.full_heal()
                self._set_message("Party fully restored!")

        pc, pr = self.level.portal
        prect = pygame.Rect(pc * TILE, pr * TILE, TILE, TILE * 2)
        if rect.colliderect(prect):
            if self.level.boss_defeated:
                self._complete_level()
            else:
                self._set_message("The way is sealed - defeat the boss ahead!")

    def _set_message(self, text, t=1.6):
        self.message = text
        self.message_timer = t

    def _start_battle(self, kind, is_level_boss=False):
        from battle import BattleScene
        self.app.change_state(BattleScene(self.app, return_scene=self, kind=kind, is_level_boss=is_level_boss))

    def _complete_level(self):
        from level_complete import LevelCompleteScene
        self.app.change_state(LevelCompleteScene(self.app))

    # ---------------- draw ----------------
    def draw(self, surface):
        self._draw_sky(surface)
        self._draw_parallax(surface)
        self._draw_tiles(surface)
        self._draw_objects(surface)
        for p in self.particles:
            p.draw(surface, self.cam_x)
        self._draw_player(surface)
        self._draw_hud(surface)

    def _draw_sky(self, surface):
        for y in range(WINDOW_HEIGHT):
            f = y / WINDOW_HEIGHT
            color = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * f) for i in range(3))
            pygame.draw.line(surface, color, (0, y), (WINDOW_WIDTH, y))

    def _draw_parallax(self, surface):
        layers = [
            (0.15, 90, (46, 30, 66)),
            (0.3, 140, (56, 38, 78)),
            (0.5, 190, (70, 48, 92)),
        ]
        for factor, base_h, color in layers:
            offset = self.cam_x * factor
            spacing = 160
            start_i = int(offset // spacing) - 1
            for i in range(start_i, start_i + int(WINDOW_WIDTH / spacing) + 3):
                hx = i * spacing - offset
                hh = base_h + 30 * math.sin(i * 1.7)
                points = [
                    (hx - spacing * 0.6, WINDOW_HEIGHT),
                    (hx, WINDOW_HEIGHT - hh),
                    (hx + spacing * 0.6, WINDOW_HEIGHT),
                ]
                pygame.draw.polygon(surface, color, points)

    def _draw_tiles(self, surface):
        c0 = max(0, int(self.cam_x // TILE) - 1)
        c1 = min(self.level.cols - 1, int((self.cam_x + WINDOW_WIDTH) // TILE) + 1)
        pulse = (math.sin(self.t * 4) + 1) / 2
        for row in range(ROWS):
            for col in range(c0, c1 + 1):
                ch = self.level.tile_at(col, row)
                if ch == '.':
                    continue
                x = col * TILE - self.cam_x
                y = row * TILE
                rect = pygame.Rect(x, y, TILE, TILE)
                is_top = row == 0 or self.level.tile_at(col, row - 1) == '.'
                if ch == '^':
                    base = CORRUPT_TILE
                    lit = tuple(int(base[i] + (CORRUPT_TILE_PULSE[i] - base[i]) * pulse * 0.5) for i in range(3))
                    pygame.draw.rect(surface, lit, rect)
                    pygame.draw.rect(surface, (40, 5, 30), rect, 2)
                else:
                    color = GROUND_TOP if is_top else GROUND
                    pygame.draw.rect(surface, color, rect)
                    pygame.draw.rect(surface, (20, 18, 26), rect, 1)

    def _world_to_screen(self, col, row):
        return col * TILE - self.cam_x, row * TILE

    def _draw_objects(self, surface):
        pulse = (math.sin(self.t * 5) + 1) / 2

        for tc, tr in self.level.normal_triggers:
            x, y = self._world_to_screen(tc, tr)
            if -TILE < x < WINDOW_WIDTH + TILE:
                self._draw_enemy_sprite(surface, x, y, ENEMY_COLOR, TILE, "!")

        if not self.level.boss_defeated and self.level.boss_trigger:
            tc, tr = self.level.boss_trigger
            x, y = self._world_to_screen(tc, tr)
            if -TILE * 2 < x < WINDOW_WIDTH + TILE * 2:
                size = TILE + 10 + int(6 * pulse)
                self._draw_enemy_sprite(surface, x - 5, y - (size - TILE), ENEMY_BOSS_COLOR, size, "")
                pf.draw(surface, "BOSS", 12, (255, 210, 150), (x + TILE / 2, y - 18), center=True)

        for rc, rr, used in self.level.restore_points:
            if used:
                continue
            x, y = self._world_to_screen(rc, rr)
            if -TILE < x < WINDOW_WIDTH + TILE:
                cx, cy = x + TILE / 2, y + TILE / 2
                glow = int(60 + 40 * pulse)
                pygame.draw.circle(surface, (glow, glow + 80, glow + 20), (int(cx), int(cy)), 14)
                pygame.draw.rect(surface, RESTORE_COLOR, (cx - 3, cy - 10, 6, 20))
                pygame.draw.rect(surface, RESTORE_COLOR, (cx - 10, cy - 3, 20, 6))

        pc, pr = self.level.portal
        x, y = self._world_to_screen(pc, pr)
        if -TILE * 2 < x < WINDOW_WIDTH + TILE * 2:
            locked = not self.level.boss_defeated
            color = PORTAL_LOCKED_COLOR if locked else PORTAL_COLOR_A
            glow = PORTAL_LOCKED_COLOR if locked else PORTAL_COLOR_B
            swirl = (math.sin(self.t * 3) + 1) / 2
            rect = pygame.Rect(x, y - TILE, TILE, TILE * 2)
            pygame.draw.ellipse(surface, glow, rect.inflate(int(10 * swirl), 6))
            pygame.draw.ellipse(surface, color, rect)
            pygame.draw.ellipse(surface, (10, 10, 14), rect, 3)
            label = "LOCKED" if locked else "EXIT"
            pf.draw(surface, label, 12, WHITE, (rect.centerx, rect.y - 16), center=True)

    def _draw_enemy_sprite(self, surface, x, y, color, size, mark):
        ui.shadow_ellipse(surface, (x + size / 2, y + size + 2), size * 0.8, 10)
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (10, 10, 10), rect, 2)
        eye_y = y + size * 0.35
        pygame.draw.rect(surface, (15, 15, 15), (x + size * 0.25, eye_y, 5, 5))
        pygame.draw.rect(surface, (15, 15, 15), (x + size * 0.65, eye_y, 5, 5))
        if mark:
            pf.draw(surface, mark, 14, WHITE, (x + size / 2, y - 4), center=True)

    def _draw_player(self, surface):
        x = self.px - self.cam_x
        y = self.py
        ui.shadow_ellipse(surface, (x + PLAYER_W / 2, y + PLAYER_H + 2), 26, 10)
        body = pygame.Rect(x, y, PLAYER_W, PLAYER_H)
        pygame.draw.rect(surface, self.leader_color, body)
        pygame.draw.rect(surface, (20, 20, 20), body, 2)
        eye_x = x + (PLAYER_W - 8 if self.facing > 0 else 8)
        pygame.draw.rect(surface, (20, 20, 20), (eye_x - 3, y + 10, 6, 6))
        if self.jump_count >= 2:
            pygame.draw.circle(surface, (255, 255, 255), (int(x + PLAYER_W / 2), int(y - 6)), 3)

    def _draw_hud(self, surface):
        ui.corruption_edge_meter(surface, WINDOW_HEIGHT, self.data.corruption.value)
        ui.status_icons(surface, (44, 64), self.data.status.active)

        panel_rect = pygame.Rect(WINDOW_WIDTH - 230, 16, 214, 20 + 26 * len(self.data.party.members))
        ui.panel(surface, panel_rect)
        for i, m in enumerate(self.data.party.members):
            yy = panel_rect.y + 10 + i * 26
            pygame.draw.rect(surface, m.color, (panel_rect.x + 10, yy, 14, 14))
            if m.is_captain:
                pygame.draw.rect(surface, (255, 215, 90), (panel_rect.x + 10, yy, 14, 14), 2)
            ui.hp_bar(surface, (panel_rect.x + 32, yy), 120, 14, max(0, m.hp), m.max_hp_total)
            pf.draw(surface, f"{m.hp}", 12, WHITE, (panel_rect.x + 160, yy - 2), shadow=False)

        pf.draw(surface, f"LEVEL {self.data.level_index + 1}", 18, WHITE, (44, 10))
        remaining = len(self.level.normal_triggers)
        boss_state = "defeated" if self.level.boss_defeated else "ahead - blocks the exit"
        pf.draw(surface, f"Buffs collected: {self.data.buffs_collected}   Skippable fights left: {remaining}", 13, WHITE, (44, 94))
        pf.draw(surface, f"Boss: {boss_state}", 13, (255, 180, 150), (44, 112))

        if self.message and self.message_timer > 0:
            pf.draw(surface, self.message, 15, (255, 230, 160), (WINDOW_WIDTH / 2, 20), center=True)
