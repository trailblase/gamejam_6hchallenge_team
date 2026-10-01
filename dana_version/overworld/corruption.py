"""Overworld corruption: a bool grid that sits on top of the tilemap and
spreads over time. Pure logic - no pygame. Corrupted tiles only slow the
leader; they never block, so they can't cut off any route."""

from data import config

CORRUPTIBLE_KINDS = {"grass", "flowers"}   # paths, water, trees and bushes never corrupt


class CorruptionGrid:
    def __init__(self, tilemap, rng, start_tile, guarded_tiles=(), arena_centers=()):
        self.w, self.h = tilemap.w, tilemap.h
        self.rng = rng
        self.grid = [[False] * self.w for _ in range(self.h)]
        self.count = 0

        r = config.CORRUPT_ARENA_RADIUS
        self.eligible = [[False] * self.w for _ in range(self.h)]
        walkable = 0
        for ty in range(self.h):
            for tx in range(self.w):
                if not tilemap.blocked(tx, ty):
                    walkable += 1
                in_arena = any(max(abs(tx - ax), abs(ty - ay)) <= r for ax, ay in arena_centers)
                self.eligible[ty][tx] = tilemap.kind(tx, ty) in CORRUPTIBLE_KINDS and not in_arena
        self.walkable = walkable
        self.cap = max(1, int(walkable * config.CORRUPT_MAX_FRACTION))
        self._seed(start_tile, guarded_tiles)

    def _far_from_start(self, tx, ty, start):
        return max(abs(tx - start[0]), abs(ty - start[1])) > config.CORRUPT_SEED_MIN_START_DIST

    def _seed(self, start, guarded_tiles):
        seeds_left = config.CORRUPT_START_SEEDS
        gr = config.CORRUPT_GUARD_RADIUS
        for gx, gy in guarded_tiles:
            if seeds_left <= 0:
                break
            near = [(x, y) for y in range(gy - gr, gy + gr + 1) for x in range(gx - gr, gx + gr + 1)
                    if self._can_corrupt(x, y) and self._far_from_start(x, y, start)]
            if near:
                self._set(*self.rng.choice(near))
                seeds_left -= 1
        pool = [(x, y) for y in range(self.h) for x in range(self.w)
                if self._can_corrupt(x, y) and self._far_from_start(x, y, start)]
        for x, y in self.rng.sample(pool, min(seeds_left, len(pool))):
            self._set(x, y)

    def _can_corrupt(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h and self.eligible[ty][tx] and not self.grid[ty][tx]

    def _set(self, tx, ty):
        self.grid[ty][tx] = True
        self.count += 1

    def is_corrupt(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h and self.grid[ty][tx]

    @property
    def capped(self):
        return self.count >= self.cap

    @property
    def fraction_of_cap(self):
        return min(1.0, self.count / self.cap)

    def spread_step(self):
        """Each corrupted tile may infect one random 4-neighbor. Tiles infected
        this step don't spread until the next one. Returns tiles infected."""
        if self.capped:
            return 0
        current = [(x, y) for y in range(self.h) for x in range(self.w) if self.grid[y][x]]
        infected = 0
        for x, y in current:
            if self.rng.random() >= config.CORRUPT_SPREAD_CHANCE:
                continue
            options = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if self._can_corrupt(x + dx, y + dy)]
            if options:
                self._set(*self.rng.choice(options))
                infected += 1
                if self.capped:
                    break
        return infected
