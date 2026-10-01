"""Overworld rules: tilemap, collision, player, follower trail, enemies,
springs and camera. Pure logic - no pygame. Positions are FEET positions
in pixels (x = center, y = bottom of the collision box)."""

import math
from collections import deque

from data import config
from data.chests import CHESTS
from data.world_map import MAP_ROWS, MAP_W, MAP_H, TILE_KINDS, BLOCKED_KINDS, ENEMY_GROUPS, BOSS_MARKERS
from overworld.corruption import CorruptionGrid

T = config.TILE


class TileMap:
    def __init__(self, rows):
        self.w, self.h = MAP_W, MAP_H
        self.kinds = []
        self.markers = {}   # char -> list of (tx, ty)
        for ty in range(self.h):
            row = rows[ty] if ty < len(rows) else ""
            row = row.ljust(self.w, ".")[: self.w]
            kinds_row = []
            for tx, ch in enumerate(row):
                if ch in TILE_KINDS:
                    kinds_row.append(TILE_KINDS[ch])
                else:
                    kinds_row.append("grass")
                    self.markers.setdefault(ch, []).append((tx, ty))
            self.kinds.append(kinds_row)

    def kind(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return self.kinds[ty][tx]
        return "tree"

    def blocked(self, tx, ty):
        return self.kind(tx, ty) in BLOCKED_KINDS

    def box_blocked(self, x, y, w, h):
        left, right = x - w / 2, x + w / 2
        top, bottom = y - h, y
        for ty in range(math.floor(top / T), math.floor((bottom - 0.01) / T) + 1):
            for tx in range(math.floor(left / T), math.floor((right - 0.01) / T) + 1):
                if self.blocked(tx, ty):
                    return True
        return False

    @property
    def pixel_size(self):
        return self.w * T, self.h * T


def tile_center_feet(tx, ty):
    """Feet position that stands in the middle of a tile."""
    return tx * T + T / 2, ty * T + T / 2 + 6


def move_with_collision(tilemap, x, y, w, h, dx, dy):
    """Axis-separated move: try X then Y, stepping up to the wall on a hit so
    the mover slides along obstacles instead of sticking."""
    x = _move_axis(tilemap, x, y, w, h, dx, 0)
    y = _move_axis(tilemap, x, y, w, h, dy, 1)
    return x, y


def _move_axis(tilemap, x, y, w, h, delta, axis):
    if delta == 0:
        return x if axis == 0 else y
    pos = [x, y]
    pos[axis] += delta
    if not tilemap.box_blocked(pos[0], pos[1], w, h):
        return pos[axis]
    pos[axis] -= delta
    step = 1 if delta > 0 else -1
    remaining = abs(delta)
    while remaining > 0:
        move = min(1, remaining) * step
        pos[axis] += move
        if tilemap.box_blocked(pos[0], pos[1], w, h):
            pos[axis] -= move
            break
        remaining -= 1
    return pos[axis]


class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.facing = (0, 1)
        self.moving = False


class Enemy:
    def __init__(self, entity_id, x, y, is_boss, key, rng):
        self.id = entity_id
        self.home = (x, y)
        self.x, self.y = x, y
        self.is_boss = is_boss
        self.key = key                # group list (normal) or boss id
        self.rng = rng
        self.target = None
        self.wait = rng.uniform(*config.ENEMY_IDLE_TIME)
        self.stun = 0.0
        self.chasing = False

    @property
    def touch_radius(self):
        return config.BOSS_TOUCH_RADIUS if self.is_boss else config.TOUCH_RADIUS

    def reset(self):
        self.x, self.y = self.home
        self.target = None
        self.stun = 0.0
        self.chasing = False

    def update(self, dt, tilemap, player):
        if self.is_boss:
            return
        if self.stun > 0:
            self.stun = max(0.0, self.stun - dt)
            self.chasing = False
            return
        w, h = config.ENEMY_BOX
        d_player = math.hypot(player.x - self.x, player.y - self.y)
        d_home = math.hypot(self.x - self.home[0], self.y - self.home[1])
        self.chasing = d_player < config.ENEMY_AGGRO_RADIUS and d_home < config.ENEMY_LEASH_RADIUS
        if self.chasing:
            self._step_toward(player.x, player.y, config.ENEMY_CHASE_SPEED, dt, tilemap, w, h)
            self.target = None
            return
        if self.target is None:
            self.wait -= dt
            if self.wait <= 0:
                ang = self.rng.uniform(0, math.tau)
                dist = self.rng.uniform(0, config.ENEMY_WANDER_RADIUS)
                self.target = (self.home[0] + math.cos(ang) * dist, self.home[1] + math.sin(ang) * dist)
            return
        arrived = self._step_toward(self.target[0], self.target[1], config.ENEMY_WANDER_SPEED, dt, tilemap, w, h)
        if arrived:
            self.target = None
            self.wait = self.rng.uniform(*config.ENEMY_IDLE_TIME)

    def _step_toward(self, tx, ty, speed, dt, tilemap, w, h):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist <= config.ENEMY_ARRIVE_DIST:
            return True
        step = min(dist, speed * dt)
        nx, ny = move_with_collision(tilemap, self.x, self.y, w, h, dx / dist * step, dy / dist * step)
        stuck = abs(nx - self.x) < 0.01 and abs(ny - self.y) < 0.01
        self.x, self.y = nx, ny
        return stuck


class Spring:
    def __init__(self, spring_id, x, y):
        self.id = spring_id
        self.x, self.y = x, y
        self.used = False


class Chest:
    def __init__(self, chest_id, tile):
        self.id = chest_id
        self.tile = tile
        self.x, self.y = tile_center_feet(*tile)
        self.opened = False


class Guide:
    """Friendly slime at the spawn. Talks; never fights or blocks."""

    def __init__(self, tile):
        self.tile = tile
        self.x, self.y = tile_center_feet(*tile)
        self.name = "Suspicious Mustache"


def check_reachability(tilemap, start_tile, targets):
    """Flood-fill walkable tiles from the start; raise if any target tile
    (name -> (tx, ty)) can't be reached."""
    seen = {start_tile}
    frontier = deque([start_tile])
    while frontier:
        x, y = frontier.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt not in seen and not tilemap.blocked(*nxt):
                seen.add(nxt)
                frontier.append(nxt)
    missing = [name for name, tile in targets.items() if tile not in seen]
    if missing:
        raise AssertionError(f"map check failed - unreachable from start: {missing}")
    return len(seen)


class World:
    def __init__(self, rng, defeated=(), springs_used=(), chests_opened=()):
        self.rng = rng
        self.map = TileMap(MAP_ROWS)
        start = self.map.markers["P"][0]
        self.start_tile = start
        self.start = tile_center_feet(*start)
        self.player = Player(*self.start)
        trail_len = max(config.FOLLOWER_DELAYS) + 1
        self.trail = deque([(self.player.x, self.player.y)] * trail_len, maxlen=trail_len)

        self.enemies = []
        for ch, group in ENEMY_GROUPS.items():
            for i, (tx, ty) in enumerate(self.map.markers.get(ch, [])):
                ent_id = f"enemy_{ch}{i}"
                if ent_id not in defeated:
                    self.enemies.append(Enemy(ent_id, *tile_center_feet(tx, ty), False, group, rng))
        for ch, boss_id in BOSS_MARKERS.items():
            for (tx, ty) in self.map.markers.get(ch, []):
                ent_id = f"boss_{boss_id}"
                if ent_id not in defeated:
                    self.enemies.append(Enemy(ent_id, *tile_center_feet(tx, ty), True, boss_id, rng))

        self.springs = []
        for i, (tx, ty) in enumerate(self.map.markers.get("H", [])):
            spring = Spring(f"spring_{i}", *tile_center_feet(tx, ty))
            spring.used = spring.id in springs_used
            self.springs.append(spring)

        self.chests = []
        for data in CHESTS:
            chest = Chest(data["id"], data["tile"])
            chest.opened = chest.id in chests_opened
            self.chests.append(chest)

        spots = self.map.markers.get("N", [])
        self.guide = Guide(spots[0]) if spots else None

        targets = {f"chest {c.id}": c.tile for c in self.chests}
        if self.guide:
            targets["guide"] = self.guide.tile
        for ch, tiles in self.map.markers.items():
            if ch in ENEMY_GROUPS or ch in BOSS_MARKERS or ch == "H":
                for i, tile in enumerate(tiles):
                    targets[f"marker {ch}{i}"] = tile
        self.reachable_tiles = check_reachability(self.map, start, targets)

        boss_tiles = [t for ch in BOSS_MARKERS for t in self.map.markers.get(ch, [])]
        guarded = [c["tile"] for c in CHESTS if c["guarded"]]
        self.corruption = CorruptionGrid(self.map, rng, start, guarded, boss_tiles)
        self.spread_timer = 0.0
        self.spread_pause = 0.0

        self.cam_x, self.cam_y = 0.0, 0.0
        self.snap_camera(config.WINDOW_W, config.WINDOW_H)

    # ------------------------------------------------------------- update
    def update(self, dt, move_x, move_y, view_w, view_h, freeze_enemies=False):
        """Advance one frame. Returns the Enemy touched this frame, or None."""
        p = self.player
        p.moving = bool(move_x or move_y)
        if p.moving:
            length = math.hypot(move_x, move_y)
            vx, vy = move_x / length, move_y / length
            p.facing = (vx, vy)
            w, h = config.PLAYER_BOX
            speed = config.PLAYER_SPEED * (config.CORRUPT_SLOW if self.leader_slowed else 1.0)
            nx, ny = move_with_collision(self.map, p.x, p.y, w, h, vx * speed * dt, vy * speed * dt)
            if (nx, ny) != (p.x, p.y):
                p.x, p.y = nx, ny
                self.trail.append((p.x, p.y))

        if not freeze_enemies:
            for enemy in self.enemies:
                enemy.update(dt, self.map, p)

        if self.spread_pause > 0:
            self.spread_pause = max(0.0, self.spread_pause - dt)
        else:
            self.spread_timer += dt
            while self.spread_timer >= config.CORRUPT_SPREAD_INTERVAL:
                self.spread_timer -= config.CORRUPT_SPREAD_INTERVAL
                self.corruption.spread_step()

        self._update_camera(dt, view_w, view_h)

        if freeze_enemies:
            return None
        for enemy in self.enemies:
            if enemy.stun > 0:
                continue
            if math.hypot(enemy.x - p.x, enemy.y - p.y) < enemy.touch_radius:
                return enemy
        return None

    def follower_positions(self):
        return [self.trail[-1 - d] for d in config.FOLLOWER_DELAYS]

    def _camera_target(self, view_w, view_h):
        map_w, map_h = self.map.pixel_size
        tx = min(max(self.player.x - view_w / 2, 0), map_w - view_w)
        ty = min(max(self.player.y - view_h / 2, 0), map_h - view_h)
        return tx, ty

    def _update_camera(self, dt, view_w, view_h):
        tx, ty = self._camera_target(view_w, view_h)
        k = min(1.0, config.CAMERA_LERP * dt)
        self.cam_x += (tx - self.cam_x) * k
        self.cam_y += (ty - self.cam_y) * k

    def snap_camera(self, view_w, view_h):
        self.cam_x, self.cam_y = self._camera_target(view_w, view_h)

    @property
    def leader_slowed(self):
        p = self.player
        return self.corruption.is_corrupt(int(p.x // T), int((p.y - 1) // T))

    def force_spread(self):
        return self.corruption.spread_step()

    # ------------------------------------------------------------ actions
    def nearby_guide(self):
        guide = self.guide
        if guide and math.hypot(guide.x - self.player.x, guide.y - self.player.y) < config.GUIDE_TALK_RADIUS:
            return guide
        return None

    def pause_spread(self, seconds):
        """Hold corruption spread after a victory. A new win refreshes the wait."""
        self.spread_pause = max(self.spread_pause, seconds)

    def nearby_chest(self):
        p = self.player
        for c in self.chests:
            if not c.opened and math.hypot(c.x - p.x, c.y - p.y) < config.CHEST_OPEN_RADIUS:
                return c
        return None

    def open_chest(self):
        chest = self.nearby_chest()
        if chest:
            chest.opened = True
        return chest

    def nearby_spring(self):
        p = self.player
        for s in self.springs:
            if not s.used and math.hypot(s.x - p.x, s.y - p.y) < config.SPRING_USE_RADIUS:
                return s
        return None

    def use_spring(self):
        spring = self.nearby_spring()
        if spring:
            spring.used = True
        return spring

    def remove_enemy(self, entity_id):
        self.enemies = [e for e in self.enemies if e.id != entity_id]

    def stun_enemy(self, entity_id):
        for e in self.enemies:
            if e.id == entity_id:
                e.stun = config.FLEE_STUN_SECONDS
                e.chasing = False

    def respawn_player(self, view_w, view_h):
        """After a game over: back to the start; surviving enemies go home."""
        self.player = Player(*self.start)
        self.trail.clear()
        self.trail.extend([self.start] * self.trail.maxlen)
        for e in self.enemies:
            e.reset()
        self.snap_camera(view_w, view_h)

    def nearest_enemy(self):
        p = self.player
        if not self.enemies:
            return None
        return min(self.enemies, key=lambda e: math.hypot(e.x - p.x, e.y - p.y))

    def teleport_near_next_boss(self, view_w, view_h):
        bosses = [e for e in self.enemies if e.is_boss]
        if not bosses:
            return None
        boss = bosses[0]
        off = config.TELEPORT_OFFSET
        w, h = config.PLAYER_BOX
        for dx, dy in ((0, off), (off, 0), (-off, 0), (0, -off), (off, off), (-off, off)):
            x, y = boss.x + dx, boss.y + dy
            if not self.map.box_blocked(x, y, w, h):
                self.player.x, self.player.y = x, y
                self.trail.clear()
                self.trail.extend([(x, y)] * self.trail.maxlen)
                self.snap_camera(view_w, view_h)
                return boss
        return None
