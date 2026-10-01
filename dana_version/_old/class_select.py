import pygame
import pixel_font as pf
import ui
from settings import WINDOW_WIDTH, WINDOW_HEIGHT, PRESET_TEAMS, CLASS_STATS, WHITE, CAPTAIN_MARK


class ClassSelectScene:
    """Step 1: pick a team of 3. Step 2: pick which of the 3 you personally
    control (the captain) - the other two just ride along as support."""

    def __init__(self, app):
        self.app = app
        self.step = "team"
        self.chosen_team = None

        card_w, card_h = 260, 340
        gap = 40
        total_w = card_w * len(PRESET_TEAMS) + gap * (len(PRESET_TEAMS) - 1)
        start_x = (WINDOW_WIDTH - total_w) / 2
        y = 160
        self.team_cards = []
        for i, team in enumerate(PRESET_TEAMS):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            self.team_cards.append({"team": team, "rect": rect, "hover": False})

        self.captain_cards = []

    def _build_captain_cards(self):
        card_w, card_h = 220, 260
        gap = 40
        total_w = card_w * len(self.chosen_team) + gap * (len(self.chosen_team) - 1)
        start_x = (WINDOW_WIDTH - total_w) / 2
        y = 180
        self.captain_cards = []
        for i, cls in enumerate(self.chosen_team):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            self.captain_cards.append({"class_name": cls, "index": i, "rect": rect, "hover": False})

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.step == "captain":
                self.step = "team"
            else:
                self.app.quit()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.step == "team":
                for card in self.team_cards:
                    if card["rect"].collidepoint(event.pos):
                        self.chosen_team = card["team"]
                        self._build_captain_cards()
                        self.step = "captain"
            else:
                for card in self.captain_cards:
                    if card["rect"].collidepoint(event.pos):
                        self._start(self.chosen_team, card["index"])

    def _start(self, team, captain_index):
        from overworld import OverworldScene
        self.app.data.new_game(team, captain_index)
        self.app.change_state(OverworldScene(self.app))

    def update(self, dt):
        mouse = pygame.mouse.get_pos()
        cards = self.team_cards if self.step == "team" else self.captain_cards
        for card in cards:
            card["hover"] = card["rect"].collidepoint(mouse)

    def draw(self, surface):
        if self.step == "team":
            self._draw_team_step(surface)
        else:
            self._draw_captain_step(surface)

    def _draw_team_step(self, surface):
        surface.fill((26, 18, 36))
        pf.draw(surface, "CHOOSE YOUR PARTY", 32, WHITE, (WINDOW_WIDTH / 2, 70), center=True)
        pf.draw(surface, "The corruption spreads. Pick a team and descend.", 14, (190, 170, 210), (WINDOW_WIDTH / 2, 112), center=True)

        for card in self.team_cards:
            rect = card["rect"]
            ui.panel(surface, rect, lit=card["hover"])
            team = card["team"]
            for j, cls in enumerate(team):
                stats = CLASS_STATS[cls]
                yy = rect.y + 24 + j * 100
                swatch = pygame.Rect(rect.x + 20, yy, 28, 28)
                pygame.draw.rect(surface, stats["color"], swatch)
                pygame.draw.rect(surface, (15, 15, 15), swatch, 2)
                pf.draw(surface, cls, 16, WHITE, (rect.x + 58, yy + 2))
                pf.draw(surface, f"HP {stats['hp']}  ATK {stats['atk']}", 11, (210, 210, 220), (rect.x + 58, yy + 30), shadow=False)
                pf.draw(surface, f"SPD {stats['spd']}  RNG {stats['rng']}", 11, (210, 210, 220), (rect.x + 58, yy + 46), shadow=False)
            pf.draw(surface, "SELECT", 15, (255, 230, 150) if card["hover"] else (180, 170, 190),
                    (rect.centerx, rect.bottom - 28), center=True, shadow=False)

    def _draw_captain_step(self, surface):
        surface.fill((22, 20, 34))
        pf.draw(surface, "CHOOSE YOUR CAPTAIN", 30, WHITE, (WINDOW_WIDTH / 2, 70), center=True)
        pf.draw(surface, "You control the captain and attack in battle.", 14, (190, 170, 210), (WINDOW_WIDTH / 2, 108), center=True)
        pf.draw(surface, "The other two follow you and passively buff you - as long as they're alive.", 13, (190, 170, 210), (WINDOW_WIDTH / 2, 128), center=True)

        for card in self.captain_cards:
            rect = card["rect"]
            ui.panel(surface, rect, lit=card["hover"])
            cls = card["class_name"]
            stats = CLASS_STATS[cls]
            swatch = pygame.Rect(rect.centerx - 24, rect.y + 24, 48, 48)
            pygame.draw.rect(surface, stats["color"], swatch)
            pygame.draw.rect(surface, CAPTAIN_MARK if card["hover"] else (15, 15, 15), swatch, 3)
            pf.draw(surface, cls, 18, WHITE, (rect.centerx, rect.y + 96), center=True)
            pf.draw(surface, f"HP {stats['hp']}  ATK {stats['atk']}", 12, (210, 210, 220), (rect.centerx, rect.y + 128), center=True, shadow=False)
            pf.draw(surface, f"SPD {stats['spd']}  RNG {stats['rng']}", 12, (210, 210, 220), (rect.centerx, rect.y + 146), center=True, shadow=False)
            pf.draw(surface, "MAKE CAPTAIN", 14, (255, 230, 150) if card["hover"] else (180, 170, 190),
                    (rect.centerx, rect.bottom - 24), center=True, shadow=False)
