"""Persistent state for one run: chosen team, leader HP, stacked rewards,
and what has been defeated. Pure logic - no pygame."""

from data import config
from data.characters import CHARACTERS
from data.enemies import ENEMIES, BOSSES
from data.rewards import REWARDS
from data.buffs import BUFFS
from battle.engine import BattleState


class RunState:
    def __init__(self, team, leader_index, rng):
        self.rng = rng
        self.team = list(team)               # character keys
        self.leader_index = leader_index
        self.atk_pct = 0.0
        self.spd_bonus = 0
        self.max_sp_bonus = 0
        self.leader_hp_bonus = 0
        self.leader_hp = self.leader_max_hp
        self.defeated = set()                # overworld entity ids, never come back
        self.bosses_defeated = set()
        self.springs_used = set()
        self.chests_opened = set()
        self.buffs = []                      # buff dicts from data/buffs.py, kept all session
        self.battles_fought = 0
        self.touched_corruption = False      # applies to the next battle only

    # ------------------------------------------------------------ party stats
    @property
    def leader_key(self):
        return self.team[self.leader_index]

    @property
    def leader_max_hp(self):
        return CHARACTERS[self.leader_key]["max_hp"] + self.leader_hp_bonus

    @property
    def max_sp(self):
        return config.BASE_MAX_SP + self.max_sp_bonus

    def party_specs(self):
        specs = []
        atk_multiplier = 1 + self.atk_pct + self.buff_total("atk_pct")
        if self.touched_corruption:
            atk_multiplier -= config.CORRUPTION_TOUCH_ATK_PENALTY
        for i, key in enumerate(self.team):
            char = CHARACTERS[key]
            specs.append({
                "char": char,
                "atk": round(char["atk"] * max(0.1, atk_multiplier)),
                "spd": char["spd"] + self.spd_bonus,
                "is_leader": i == self.leader_index,
            })
        return specs

    # ---------------------------------------------------------------- battles
    @staticmethod
    def enemy_defs_for(encounter_kind, key):
        if encounter_kind == "boss":
            return [BOSSES[key]]
        return [ENEMIES[name] for name in key]

    def make_battle(self, enemy_defs, can_flee):
        return BattleState(
            party_specs=self.party_specs(),
            leader_hp=self.leader_hp,
            leader_max_hp=self.leader_max_hp,
            enemy_defs=enemy_defs,
            rng=self.rng,
            can_flee=can_flee,
            max_sp=self.max_sp,
            modifiers=self.battle_modifiers(),
        )

    def finish_battle(self, battle):
        self.leader_hp = battle.leader_hp
        self.battles_fought += 1
        self.touched_corruption = False

    def record_defeat(self, entity_id, boss_id=None):
        self.defeated.add(entity_id)
        if boss_id:
            self.bosses_defeated.add(boss_id)

    @property
    def all_bosses_defeated(self):
        return len(self.bosses_defeated) >= config.BOSSES_TO_WIN

    # ---------------------------------------------------------------- rewards
    def roll_rewards(self):
        return self.rng.sample(REWARDS, config.REWARD_CHOICES)

    def apply_reward(self, reward):
        effect, value = reward["effect"], reward["value"]
        if effect == "atk_pct":
            self.atk_pct += value
        elif effect == "leader_max_hp":
            self.leader_hp_bonus += value
            self.heal(value)
        elif effect == "max_sp":
            self.max_sp_bonus += value
        elif effect == "spd":
            self.spd_bonus += value
        elif effect == "heal":
            self.heal(value)
        else:
            raise ValueError(f"unknown reward effect {effect}")

    # ------------------------------------------------------------------ buffs
    def buff_total(self, key):
        return sum(b["mod"].get(key, 0) for b in self.buffs)

    def battle_modifiers(self):
        """What the battle engine reads at battle start. ATK is already folded
        into party_specs(); these are the rest."""
        return {"start_sp": self.buff_total("start_sp"), "ward": self.buff_total("ward")}

    def roll_buff(self):
        """Random buff, preferring ones not owned yet so a few chests show
        the whole set; repeats only once all have been found."""
        owned = {b["id"] for b in self.buffs}
        fresh = [b for b in BUFFS if b["id"] not in owned]
        return self.rng.choice(fresh or BUFFS)

    def apply_buff(self, buff):
        self.buffs.append(buff)
        heal_pct = buff["mod"].get("heal_pct", 0)
        if heal_pct:
            self.heal(round(self.leader_max_hp * heal_pct))

    def victory_heal(self):
        self.heal(round(self.leader_max_hp * config.VICTORY_HEAL_PCT))

    def heal(self, amount):
        self.leader_hp = min(self.leader_max_hp, self.leader_hp + amount)

    def damage_leader(self, amount):
        before = self.leader_hp
        self.leader_hp = max(0, self.leader_hp - amount)
        return before - self.leader_hp

    def touch_corruption(self):
        self.touched_corruption = True

    def full_heal(self):
        self.leader_hp = self.leader_max_hp

    def retry(self):
        """Game over -> respawn with full HP. Defeats and rewards are kept."""
        self.full_heal()
