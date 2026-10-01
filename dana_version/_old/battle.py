import random
import pygame
import pixel_font as pf
import ui
from settings import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GRID_COLS, GRID_ROWS, GRID_ORIGIN, CELL,
    WHITE, OBSTACLE_COLOR, HAZARD_FIRE, HAZARD_ICE, HAZARD_VOID, PANEL_BORDER_LIT,
    CAPTAIN_MARK
)
from enemies import build_encounter
import items as items_mod

HAZARD_COLORS = [HAZARD_FIRE, HAZARD_ICE, HAZARD_VOID]
ENEMY_POWER_STEP_ROUNDS = 3
HAZARD_SPAWN_ROUNDS = 2
ENEMY_ACT_DELAY = 0.9
CORRUPTION_PUSHBACK_NORMAL = 7
CORRUPTION_PUSHBACK_BOSS = 18
BOSS_LIFESTEAL_FRAC = 0.3


def cell_center(col, row):
    x = GRID_ORIGIN[0] + col * CELL + CELL // 2
    y = GRID_ORIGIN[1] + row * CELL + CELL // 2
    return x, y


def line_clear(obstacles, start, end):
    c0, c1 = sorted((start[0], end[0]))
    if c1 - c0 <= 1:
        return True
    obstacle_cols = {c for (c, r) in obstacles}
    return not any(c0 < c < c1 for c in obstacle_cols)


class FloatText:
    def __init__(self, pos, text, color):
        self.x, self.y = pos
        self.text = text
        self.color = color
        self.timer = 1.0

    def update(self, dt):
        self.y -= 40 * dt
        self.timer -= dt
        return self.timer > 0

    def draw(self, surface):
        pf.draw(surface, self.text, 18, self.color, (self.x, self.y), center=True)


class BattleScene:
    def __init__(self, app, return_scene, kind="normal", is_level_boss=False):
        self.app = app
        self.data = app.data
        self.return_scene = return_scene
        self.level = return_scene.level
        self.kind = kind
        self.is_level_boss = is_level_boss
        self.is_final_boss = (kind == "final_boss")

        self.data.party.ready_for_battle()
        self.captain = self.data.party.captain
        self.party_units = self.data.party.alive_members()
        self.enemies = build_encounter(kind, self.data.level_index, seed=random.randint(0, 999999))

        if self.is_final_boss:
            self.captain.shield = sum(m.max_hp_total for m in self.party_units)

        self._place_units()
        self.obstacles = self._place_obstacles()

        self.hazards = {}
        self.round_num = 1
        self.phase = "player"  # player, enemy, environment, victory, defeat
        self.captain_acted = False
        self.action_mode = None

        self.enemy_queue = []
        self.enemy_act_timer = 0.0

        self.floaters = []
        self.message = ""
        self.message_timer = 0.0
        self.turn_banner = "Your move, captain"

        self.buttons = {}
        self._build_buttons()

        self.reward_item = None
        self.reward_recipient = None
        self.continue_button = ui.Button((WINDOW_WIDTH / 2 - 100, WINDOW_HEIGHT - 90, 200, 50), "CONTINUE")
        self.flee_confirm = False

    # ---------------- setup ----------------
    def _place_units(self):
        rows = list(range(GRID_ROWS))
        occupied = set()
        party_col = 1
        for i, u in enumerate(self.party_units):
            r = rows[i % GRID_ROWS]
            u.grid_pos = (party_col, r)
            occupied.add((party_col, r))
        for i, e in enumerate(self.enemies):
            col = min(2 + i, GRID_COLS - 3)
            r = rows[i % GRID_ROWS]
            while (col, r) in occupied:
                r = (r + 1) % GRID_ROWS
            e.grid_pos = (col, r)
            occupied.add((col, r))
        self._occupied_cells = occupied

    def _place_obstacles(self):
        rng = random.Random(500 + self.data.level_index)
        obstacles = set()
        n = 2 + self.data.level_index
        lo, hi = 2, GRID_COLS - 3
        for _ in range(n):
            col = rng.randint(lo, max(lo, hi))
            row = rng.randint(0, GRID_ROWS - 1)
            if (col, row) in getattr(self, "_occupied_cells", set()):
                continue
            obstacles.add((col, row))
        return obstacles

    def _build_buttons(self):
        bx = WINDOW_WIDTH - 230
        by = WINDOW_HEIGHT - 212
        self.buttons["attack"] = ui.Button((bx, by, 190, 44), "ATTACK")
        self.buttons["block"] = ui.Button((bx, by + 52, 190, 44), "BLOCK")
        self.buttons["end"] = ui.Button((bx, by + 104, 190, 44), "END TURN")
        self.buttons["flee"] = ui.Button((bx, by + 156, 190, 40), "FLEE BATTLE")

    # ---------------- helpers ----------------
    def targets_in_range(self, unit):
        result = []
        for e in self.enemies:
            if not e.alive:
                continue
            dist = abs(unit.grid_pos[0] - e.grid_pos[0])
            if dist <= unit.rng and line_clear(self.obstacles, unit.grid_pos, e.grid_pos):
                result.append(e)
        return result

    def _push_float(self, grid_pos, text, color):
        x, y = cell_center(*grid_pos)
        self.floaters.append(FloatText((x, y - 20), text, color))

    def _set_message(self, text, t=1.4):
        self.message = text
        self.message_timer = t

    # ---------------- captain actions ----------------
    def do_attack(self, target):
        unit = self.captain
        self.turn_banner = f"{unit.name} (Captain) attacks {target.type_name}!"
        dmg = unit.atk + random.randint(-2, 2)
        dealt = target.take_damage(dmg)
        self._push_float(target.grid_pos, f"-{dealt}", (255, 90, 90))
        self._set_message(f"{unit.name} hits {target.type_name} for {dealt}!")

        if self.is_final_boss and dealt > 0:
            heal = max(1, round(dealt * BOSS_LIFESTEAL_FRAC))
            unit.heal(heal)
            self._push_float(unit.grid_pos, f"+{heal}", (120, 255, 150))

        if not target.alive:
            self._set_message(f"{target.type_name} defeated!")
            self._on_enemy_killed(target)
        self._advance_actor()

    def do_block(self):
        self.captain.blocking = True
        self.turn_banner = f"{self.captain.name} (Captain) braces to block."
        self._advance_actor()

    def do_end_turn(self):
        self.turn_banner = f"{self.captain.name} (Captain) passes the turn."
        self._advance_actor()

    def do_flee(self):
        self._set_message("You disengage and retreat...")
        self.app.change_state(self.return_scene)

    def _on_enemy_killed(self, enemy):
        pushback = CORRUPTION_PUSHBACK_BOSS if (self.is_level_boss or self.is_final_boss) else CORRUPTION_PUSHBACK_NORMAL
        self.data.corruption.add(-pushback)

    def _advance_actor(self):
        self.action_mode = None
        self.captain_acted = True
        self._start_enemy_phase()

    # ---------------- enemy phase ----------------
    def _start_enemy_phase(self):
        self.phase = "enemy"
        self.turn_banner = "Enemy turn"
        self.enemy_queue = sorted([e for e in self.enemies if e.alive], key=lambda e: -e.spd)
        self.enemy_act_timer = 0.4

    def _enemy_act(self, enemy):
        targets = []
        for u in self.party_units:
            if not u.alive:
                continue
            dist = abs(enemy.grid_pos[0] - u.grid_pos[0])
            if dist <= enemy.rng and line_clear(self.obstacles, enemy.grid_pos, u.grid_pos):
                targets.append(u)
        if not targets:
            self._set_message(f"{enemy.type_name} can't find a target.")
            return
        target = min(targets, key=lambda u: u.hp)
        self.turn_banner = f"{enemy.type_name} attacks {target.name}!"
        dmg = enemy.atk + random.randint(-1, 2)
        dealt = target.take_damage(dmg)
        self._push_float(target.grid_pos, f"-{dealt}", (255, 150, 90))
        self._set_message(f"{enemy.type_name} hits {target.name} for {dealt}!")

    def _finish_enemy_phase(self):
        self.phase = "environment"

    # ---------------- environment ----------------
    def _environment_tick(self):
        rng = random.Random()
        if self.round_num % HAZARD_SPAWN_ROUNDS == 0:
            tries = 0
            while tries < 10:
                col = rng.randint(0, GRID_COLS - 1)
                row = rng.randint(0, GRID_ROWS - 1)
                if (col, row) not in self.obstacles and (col, row) not in self.hazards:
                    self.hazards[(col, row)] = rng.choice(HAZARD_COLORS)
                    break
                tries += 1

        if self.round_num % ENEMY_POWER_STEP_ROUNDS == 0:
            for e in self.enemies:
                if e.alive:
                    e.buff(0.15)
            self._set_message("The battlefield grows more dangerous...")

        for pos, color in self.hazards.items():
            for u in self.party_units:
                if u.alive and u.grid_pos == pos:
                    dealt = u.take_damage(4)
                    self._push_float(u.grid_pos, f"-{dealt}", (255, 200, 90))
            for e in self.enemies:
                if e.alive and e.grid_pos == pos:
                    e.take_damage(4)

        if self.data.corruption.is_critical:
            for u in self.party_units:
                if u.alive:
                    dealt = u.take_damage(6)
                    self._push_float(u.grid_pos, f"-{dealt}", (230, 60, 200))
            self._set_message("Corruption surges! The party takes heavy damage!")
        else:
            self.data.corruption.add(1.0)

        self.round_num += 1

        if all(not e.alive for e in self.enemies):
            self._start_victory()
            return
        if self.data.party.is_wiped():
            self.phase = "defeat"
            return

        self.captain.blocking = False
        self.captain_acted = False
        self.phase = "player"
        self.turn_banner = "Your move, captain"

    def _start_victory(self):
        self.phase = "victory"
        if self.kind == "normal":
            self.data.buffs_collected += 1
        item = items_mod.random_item(self.data.level_index)
        recipient = items_mod.best_recipient(self.data.party.members, item)
        recipient.equip(item)
        self.reward_item = item
        self.reward_recipient = recipient
        if self.is_level_boss:
            self.level.boss_defeated = True

    # ---------------- event / update ----------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        mouse_pos = event.pos

        if self.phase == "victory":
            if self.continue_button.rect.collidepoint(mouse_pos):
                self.app.change_state(self.return_scene)
            return
        if self.phase == "defeat":
            from game_over import GameOverScene
            self.app.change_state(GameOverScene(self.app))
            return

        if self.phase != "player" or self.captain_acted or not self.captain.alive:
            return

        if self.action_mode == "attack":
            for e in self.targets_in_range(self.captain):
                ex, ey = cell_center(*e.grid_pos)
                rect = pygame.Rect(ex - CELL // 2, ey - CELL // 2, CELL, CELL)
                if rect.collidepoint(mouse_pos):
                    self.do_attack(e)
                    return
            self.action_mode = None
            return

        if self.buttons["attack"].rect.collidepoint(mouse_pos):
            if self.targets_in_range(self.captain):
                self.action_mode = "attack"
            else:
                self._set_message("No targets in range!")
        elif self.buttons["block"].rect.collidepoint(mouse_pos):
            self.do_block()
        elif self.buttons["end"].rect.collidepoint(mouse_pos):
            self.do_end_turn()
        elif self.buttons["flee"].rect.collidepoint(mouse_pos):
            self.do_flee()

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
        self.floaters = [f for f in self.floaters if f.update(dt)]

        for btn in self.buttons.values():
            btn.update(pygame.mouse.get_pos())
        self.continue_button.update(pygame.mouse.get_pos())

        if self.phase == "enemy":
            self.enemy_act_timer -= dt
            if self.enemy_act_timer <= 0:
                if self.enemy_queue:
                    enemy = self.enemy_queue.pop(0)
                    if enemy.alive:
                        self._enemy_act(enemy)
                        if self.data.party.is_wiped():
                            self.phase = "defeat"
                            return
                    self.enemy_act_timer = ENEMY_ACT_DELAY
                else:
                    self._finish_enemy_phase()
        elif self.phase == "environment":
            self._environment_tick()

    # ---------------- draw ----------------
    def draw(self, surface):
        surface.fill((22, 16, 30))
        self._draw_grid(surface)
        self._draw_units(surface)
        for f in self.floaters:
            f.draw(surface)
        self._draw_hud(surface)

        if self.phase == "player":
            self._draw_action_panel(surface)
        if self.phase == "victory":
            self._draw_victory(surface)
        if self.phase == "defeat":
            pf.draw(surface, "YOUR PARTY HAS FALLEN", 30, (255, 80, 80), (WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2), center=True)

    def _draw_grid(self, surface):
        can_select = self.phase == "player" and not self.captain_acted and self.action_mode == "attack"
        valid_targets = self.targets_in_range(self.captain) if can_select else []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                x = GRID_ORIGIN[0] + col * CELL
                y = GRID_ORIGIN[1] + row * CELL
                rect = pygame.Rect(x, y, CELL - 4, CELL - 4)
                color = (40, 34, 52)
                if (col, row) in self.hazards:
                    hz = self.hazards[(col, row)]
                    color = tuple(c // 3 for c in hz)
                pygame.draw.rect(surface, color, rect)
                if (col, row) in self.hazards:
                    pygame.draw.rect(surface, self.hazards[(col, row)], rect, 3)
                else:
                    pygame.draw.rect(surface, (55, 48, 68), rect, 1)
                if (col, row) in self.obstacles:
                    inner = rect.inflate(-14, -14)
                    pygame.draw.rect(surface, OBSTACLE_COLOR, inner)
                    pygame.draw.rect(surface, (20, 18, 26), inner, 2)

        for e in valid_targets:
            x, y = cell_center(*e.grid_pos)
            rect = pygame.Rect(x - CELL // 2, y - CELL // 2, CELL - 4, CELL - 4)
            pygame.draw.rect(surface, (255, 230, 90), rect, 4)

    def _draw_units(self, surface):
        for u in self.party_units:
            if not u.alive:
                continue
            x, y = cell_center(*u.grid_pos)
            ui.shadow_ellipse(surface, (x, y + 22), 36, 12)
            size = 34 if u.is_captain else 26
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(surface, u.color, rect)
            border = CAPTAIN_MARK if u.is_captain else (20, 20, 20)
            pygame.draw.rect(surface, border, rect, 3 if u.is_captain else 2)
            if u.blocking:
                pygame.draw.rect(surface, (120, 200, 255), rect.inflate(8, 8), 2)
            if u.is_captain and u.shield > 0:
                ui.shield_bar(surface, (x - 22, y - 46), 44, 5, u.shield, u.max_hp_total)
            ui.hp_bar(surface, (x - 22, y - 34), 44, 8, max(0, u.hp), u.max_hp_total)
            label = "CAPTAIN" if u.is_captain else u.class_name[:3].upper()
            pf.draw(surface, label, 10, WHITE, (x, y + 28), center=True, shadow=False)

        for e in self.enemies:
            if not e.alive:
                continue
            x, y = cell_center(*e.grid_pos)
            ui.shadow_ellipse(surface, (x, y + 22), 36, 12)
            size = 34
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(surface, e.color, rect)
            pygame.draw.polygon(surface, (10, 10, 10), [(x, y - size // 2), (x - size // 2, y + size // 2), (x + size // 2, y + size // 2)], 2)
            ui.hp_bar(surface, (x - 24, y - 36), 48, 8, max(0, e.hp), e.max_hp)
            pf.draw(surface, e.type_name[:8], 11, WHITE, (x, y + 28), center=True, shadow=False)

    def _draw_hud(self, surface):
        pf.draw(surface, f"ROUND {self.round_num}", 18, WHITE, (20, 10))
        ui.corruption_edge_meter(surface, WINDOW_HEIGHT, self.data.corruption.value)
        pf.draw(surface, self.turn_banner, 18, (255, 225, 170), (WINDOW_WIDTH / 2, 36), center=True)
        if self.message and self.message_timer > 0:
            pf.draw(surface, self.message, 15, (220, 220, 255), (WINDOW_WIDTH / 2, 62), center=True)
        phase_label = {"player": "YOUR TURN", "enemy": "ENEMY TURN", "environment": "..."}.get(self.phase, "")
        pf.draw(surface, phase_label, 14, (200, 200, 220), (WINDOW_WIDTH - 20, 12))

    def _draw_action_panel(self, surface):
        if not self.captain.alive:
            return
        panel_rect = pygame.Rect(WINDOW_WIDTH - 250, WINDOW_HEIGHT - 232, 230, 220)
        ui.panel(surface, panel_rect, lit=True)
        pf.draw(surface, f"{self.captain.name}'s turn", 16, self.captain.color, (panel_rect.x + 18, panel_rect.y + 10))
        disabled = self.captain_acted
        for key in ("attack", "block", "end", "flee"):
            self.buttons[key].enabled = not disabled or key == "flee"
            self.buttons[key].draw(surface)
        if self.action_mode == "attack":
            pf.draw(surface, "Pick a glowing target", 13, (255, 230, 160), (panel_rect.x + 18, panel_rect.y - 20))

    def _draw_victory(self, surface):
        s = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        surface.blit(s, (0, 0))
        panel_rect = pygame.Rect(WINDOW_WIDTH / 2 - 220, WINDOW_HEIGHT / 2 - 150, 440, 280)
        ui.panel(surface, panel_rect, lit=True)
        title = "BOSS DEFEATED!" if (self.is_level_boss or self.is_final_boss) else "VICTORY!"
        pf.draw(surface, title, 26, (255, 220, 120), (WINDOW_WIDTH / 2, panel_rect.y + 34), center=True)
        pf.draw(surface, "Corruption pushed back!", 14, (190, 255, 210), (WINDOW_WIDTH / 2, panel_rect.y + 64), center=True)
        if self.reward_item:
            label = "Permanent buff gained:" if self.kind == "normal" else f"{self.reward_recipient.name} found:"
            pf.draw(surface, label, 15, WHITE, (WINDOW_WIDTH / 2, panel_rect.y + 100), center=True)
            pf.draw(surface, self.reward_item.name, 18, (170, 220, 255), (WINDOW_WIDTH / 2, panel_rect.y + 130), center=True)
            pf.draw(surface, self.reward_item.describe(), 14, (170, 255, 190), (WINDOW_WIDTH / 2, panel_rect.y + 160), center=True)
        self.continue_button.draw(surface)
