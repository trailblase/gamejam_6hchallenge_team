import random

ROWS = 13
GROUND_ROW = 11

LEVEL_COUNT = 5


class Level:
    def __init__(self, index):
        self.index = index
        self.is_miniboss = (index == 2)   # level 3 (0-indexed 2)
        self.is_boss = (index == 4)       # level 5 (0-indexed 4) - the final boss
        self.cols = 58 + index * 10
        self.corrupt_frac = 0.06 + index * 0.08
        self.tiles = []          # list of rows of chars
        self.normal_triggers = []   # [col, row] - skippable, grant a permanent buff
        self.restore_points = []    # [col, row, used]
        self.boss_trigger = None    # [col, row] - mandatory, guards the portal
        self.boss_kind = "miniboss" if self.is_miniboss else ("final_boss" if self.is_boss else "level_boss")
        self.boss_defeated = False
        self.portal = None
        self.player_start = (2, GROUND_ROW - 1)
        self._generate()

    def _generate(self):
        rng = random.Random(1000 + self.index)
        cols = self.cols
        grid = [['.' for _ in range(cols)] for _ in range(ROWS)]

        pit_cols = set()
        c = 10
        while c < cols - 8:
            if rng.random() < 0.35:
                width = rng.choice([1, 1, 2])
                for w in range(width):
                    if c + w < cols:
                        pit_cols.add(c + w)
                c += width + rng.randint(4, 8)
            else:
                c += rng.randint(3, 6)

        for col in range(cols):
            if col in pit_cols:
                continue
            grid[GROUND_ROW][col] = '#'
            for r in range(GROUND_ROW + 1, ROWS):
                grid[r][col] = '#'

        num_platforms = 6 + self.index * 2
        for _ in range(num_platforms):
            pr = rng.randint(5, GROUND_ROW - 2)
            pc = rng.randint(8, cols - 8)
            width = rng.randint(2, 5)
            for w in range(width):
                if pc + w < cols:
                    grid[pr][pc + w] = '#'

        safe_zone = 6
        for r in range(ROWS):
            for col in range(cols):
                if grid[r][col] == '#' and col > safe_zone:
                    if rng.random() < self.corrupt_frac:
                        grid[r][col] = '^'

        self.tiles = grid

        # 6-7 skippable normal encounters spread across the level, leaving
        # headroom near the very end for the mandatory boss.
        n_normal = 6 if self.index < 3 else 7
        spread_end = cols - 16
        trigger_cols = []
        for i in range(n_normal):
            frac = (i + 1) / (n_normal + 1)
            trigger_cols.append(10 + int((spread_end - 10) * frac))

        placed_cols = set()
        for tc in trigger_cols:
            col, row = self._nearest_surface(tc, placed_cols)
            placed_cols.add(col)
            self.normal_triggers.append([col, row - 1])

        # a couple of full-heal checkpoints, one-use each
        restore_cols = [int(cols * 0.35), int(cols * 0.68)]
        for rc in restore_cols:
            col, row = self._nearest_surface(rc, placed_cols)
            placed_cols.add(col)
            self.restore_points.append([col, row - 1, False])

        boss_col, brow = self._nearest_surface(cols - 8, placed_cols)
        self.boss_trigger = [boss_col, brow - 1]

        portal_col, prow = self._nearest_surface(cols - 3, placed_cols)
        self.portal = (portal_col, prow - 1)

        start_col, start_row = self._nearest_surface(2, set())
        self.player_start = (start_col, start_row - 1)

    def _nearest_surface(self, target_col, avoid_cols):
        """Find the nearest column (not already used) that has solid
        ground, searching outward from target_col. Guarantees every
        spawn point lands on real ground instead of silently vanishing
        into a pit."""
        for radius in range(0, self.cols):
            for col in (target_col - radius, target_col + radius):
                if col < 0 or col >= self.cols or col in avoid_cols:
                    continue
                row = self._surface_row(col)
                if row is not None:
                    return col, row
        return max(0, min(self.cols - 1, target_col)), GROUND_ROW

    def _surface_row(self, col):
        for r in range(ROWS):
            if 0 <= col < self.cols and self.tiles[r][col] in ('#', '^'):
                return r
        return None

    def tile_at(self, col, row):
        if 0 <= row < ROWS and 0 <= col < self.cols:
            return self.tiles[row][col]
        return '.'

    def is_solid(self, col, row):
        return self.tile_at(col, row) in ('#', '^')

    def is_corrupt(self, col, row):
        return self.tile_at(col, row) == '^'

    def pixel_width(self, tile_size):
        return self.cols * tile_size
