"""Battle rules. Pure logic - NO pygame. Every state change is reported as
an event dict so the scene can animate it and a headless script can run
whole battles. Deterministic for a given random.Random seed.

Flow:
    state = BattleState(...)          # state.start_events holds opening events
    while state.outcome is None:
        if state.current.side == "party":
            events = state.apply_action({"kind": "attack", "target": uid})
        else:
            events = state.take_enemy_turn()
"""

import math

from data import config

ACTION_KINDS = ("attack", "skill", "block", "flee")


def calculate_damage(attacker, multiplier, rng):
    lo, hi = config.DAMAGE_VARIANCE
    return max(config.MIN_DAMAGE, round(attacker.atk * multiplier * rng.uniform(lo, hi)))


def _event(kind, log, **fields):
    fields["type"] = kind
    fields["log"] = log
    return fields


class PartyUnit:
    """Followers and leader alike. No HP here: the leader's HP lives on the
    BattleState, and followers can never be hit."""
    side = "party"

    def __init__(self, uid, spec):
        char = spec["char"]
        self.uid = uid
        self.name = char["name"]
        self.char = char
        self.color = char["color"]
        self.atk = spec["atk"]
        self.spd = spec["spd"]
        self.is_leader = spec["is_leader"]
        self.gauge = 0
        self.alive = True


class EnemyUnit:
    side = "enemy"

    def __init__(self, uid, data, display_name):
        self.uid = uid
        self.data = data
        self.name = display_name
        self.color = data["color"]
        self.size = data["size"]
        self.max_hp = data["max_hp"]
        self.hp = self.max_hp
        self.spd = data["spd"]
        self.is_boss = data.get("is_boss", False)
        self.gauge = 0
        self.alive = True
        self.intent = None
        self.charging = False
        self.last_was_charge = False
        self.phase2 = False


class BattleState:
    def __init__(self, party_specs, leader_hp, leader_max_hp, enemy_defs, rng,
                 can_flee=True, max_sp=config.BASE_MAX_SP, modifiers=None):
        """modifiers (optional, from overworld buffs): start_sp = extra SP at
        the start, ward = number of enemy hits on the leader auto-blocked."""
        modifiers = modifiers or {}
        self.rng = rng
        self.party = [PartyUnit(f"p{i}", spec) for i, spec in enumerate(party_specs)]
        self.leader = next(p for p in self.party if p.is_leader)
        self.leader_hp = leader_hp
        self.leader_max_hp = leader_max_hp
        self.enemies = self._build_enemies(enemy_defs)
        self.is_boss_fight = any(e.is_boss for e in self.enemies)
        self.can_flee = can_flee and not self.is_boss_fight
        self.max_sp = max_sp
        self.sp = min(config.START_SP + modifiers.get("start_sp", 0), max_sp)
        self.ward = modifiers.get("ward", 0)
        self.guard_by = None          # uid of the member whose Block protects the leader
        self.outcome = None           # None | "victory" | "defeat" | "fled"
        self.current = None
        self.party_actions = 0

        for unit in self.units():
            unit.gauge = rng.randint(0, config.GAUGE_HEAD_START_MAX)

        self.start_events = []
        for enemy in self.enemies:
            self.start_events.append(self._choose_intent(enemy))
        self.start_events += self._advance()

    def _build_enemies(self, defs):
        counts = {}
        for d in defs:
            counts[d["name"]] = counts.get(d["name"], 0) + 1
        seen = {}
        enemies = []
        for i, d in enumerate(defs):
            name = d["name"]
            if counts[name] > 1:
                seen[name] = seen.get(name, 0) + 1
                name = f"{name} {chr(ord('A') + seen[name] - 1)}"
            enemies.append(EnemyUnit(f"e{i}", d, name))
        return enemies

    # ------------------------------------------------------------- queries
    def units(self):
        """Every unit that can still act, in fixed tie-break order."""
        return self.party + [e for e in self.enemies if e.alive]

    def alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def unit(self, uid):
        for u in self.party + self.enemies:
            if u.uid == uid:
                return u
        raise KeyError(uid)

    def skill_status(self, member):
        cost = member.char["skill"]["sp_cost"]
        if self.sp < cost:
            return False, f"Need {cost} SP (have {self.sp})"
        return True, ""

    def flee_status(self):
        if not self.can_flee:
            return False, "Can't flee from a boss"
        return True, ""

    def predict(self, count):
        """Next `count` actors, simulated on a copy of the gauges."""
        entries = [[u.uid, u.spd, u.gauge] for u in self.units()]
        return [self._simulate_next(entries) for _ in range(count)]

    def timeline(self):
        head = [self.current.uid] if self.current else []
        return head + self.predict(config.TIMELINE_LENGTH - len(head))

    @staticmethod
    def _simulate_next(entries):
        threshold = config.GAUGE_THRESHOLD
        ready = [e for e in entries if e[2] >= threshold]
        if not ready:
            steps = min(math.ceil((threshold - e[2]) / e[1]) for e in entries)
            for e in entries:
                e[2] += e[1] * steps
            ready = [e for e in entries if e[2] >= threshold]
        actor = max(ready, key=lambda e: e[2])   # max() keeps the first on ties
        actor[2] -= threshold
        return actor[0]

    # ------------------------------------------------------------ turn flow
    def _advance(self):
        if self.outcome:
            return []
        units = self.units()
        entries = [[u.uid, u.spd, u.gauge] for u in units]
        uid = self._simulate_next(entries)
        for u, e in zip(units, entries):
            u.gauge = e[2]
        self.current = self.unit(uid)
        events = []
        if self.current.side == "party" and self.guard_by == self.current.uid:
            self.guard_by = None
            events.append(_event("guard_end", f"{self.current.name}'s guard ends", uid=self.current.uid))
        events.append(_event("turn_start", f"-- {self.current.name}'s turn --",
                             uid=self.current.uid, timeline=self.timeline()))
        return events

    # --------------------------------------------------------- party actions
    def apply_action(self, action):
        if self.outcome:
            raise ValueError("battle is over")
        member = self.current
        if member is None or member.side != "party":
            raise ValueError("not a party member's turn")
        kind = action.get("kind")
        if kind not in ACTION_KINDS:
            raise ValueError(f"unknown action {kind}")

        events = []
        if kind == "attack":
            target = self._pick_target(action.get("target"))
            mult = member.char["basic_attack"]["multiplier"]
            events += self._hit_enemy(member, target, calculate_damage(member, mult, self.rng),
                                      member.char["basic_attack"]["name"])
            events += self._gain_sp(config.SP_PER_ATTACK)
        elif kind == "skill":
            ok, reason = self.skill_status(member)
            if not ok:
                raise ValueError(reason)
            skill = member.char["skill"]
            self.sp -= skill["sp_cost"]
            events.append(_event("sp", f"SP {self.sp}/{self.max_sp}", sp=self.sp, max_sp=self.max_sp))
            events += self._use_skill(member, skill, action.get("target"))
        elif kind == "block":
            self.guard_by = member.uid
            events.append(_event("guard", f"{member.name} guards the leader", uid=member.uid,
                                 leader=self.leader.uid))
        elif kind == "flee":
            ok, reason = self.flee_status()
            if not ok:
                raise ValueError(reason)
            loss = int(self.leader_hp * config.FLEE_HP_COST_PCT)
            self.leader_hp -= loss
            self.outcome = "fled"
            events.append(_event("flee", f"The party flees! Leader loses {loss} HP "
                                         f"({self.leader_hp}/{self.leader_max_hp})",
                                 uid=self.leader.uid, amount=loss, hp=self.leader_hp,
                                 max_hp=self.leader_max_hp))

        self.party_actions += 1
        events += self._check_victory()
        events += self._advance()
        return events

    def _pick_target(self, uid):
        alive = self.alive_enemies()
        for e in alive:
            if e.uid == uid:
                return e
        return alive[0]

    def _use_skill(self, member, skill, target_uid):
        effect = skill["effect"]
        if effect == "single_damage":
            target = self._pick_target(target_uid)
            return self._hit_enemy(member, target, calculate_damage(member, skill["multiplier"], self.rng),
                                   skill["name"])
        if effect == "aoe_damage":
            events = []
            for target in self.alive_enemies():
                events += self._hit_enemy(member, target,
                                          calculate_damage(member, skill["multiplier"], self.rng),
                                          skill["name"])
            return events
        if effect == "heal_leader":
            before = self.leader_hp
            self.leader_hp = min(self.leader_max_hp, self.leader_hp + skill["amount"])
            healed = self.leader_hp - before
            return [_event("heal", f"{member.name} used {skill['name']}: leader +{healed} HP "
                                   f"({self.leader_hp}/{self.leader_max_hp})",
                           uid=self.leader.uid, source=member.uid, amount=healed,
                           hp=self.leader_hp, max_hp=self.leader_max_hp)]
        raise ValueError(f"unknown skill effect {effect}")

    def _gain_sp(self, amount):
        before = self.sp
        self.sp = max(0, min(self.max_sp, self.sp + amount))
        if self.sp == before:
            return []
        return [_event("sp", f"SP {self.sp}/{self.max_sp}", sp=self.sp, max_sp=self.max_sp)]

    def _hit_enemy(self, source, enemy, amount, move_name):
        if not enemy.alive:
            return []
        enemy.hp = max(0, enemy.hp - amount)
        events = [_event("damage", f"{source.name} used {move_name} on {enemy.name}: {amount} dmg "
                                   f"(HP {enemy.hp}/{enemy.max_hp})",
                         uid=enemy.uid, source=source.uid, amount=amount,
                         hp=enemy.hp, max_hp=enemy.max_hp)]
        if enemy.hp == 0:
            enemy.alive = False
            enemy.charging = False
            events.append(_event("death", f"{enemy.name} is defeated", uid=enemy.uid))
        elif enemy.is_boss and not enemy.phase2 and enemy.hp <= enemy.max_hp * config.BOSS_PHASE_HP_PCT:
            enemy.phase2 = True
            events.append(_event("phase_change", enemy.data.get("phase_text", f"{enemy.name} grows furious!"),
                                 uid=enemy.uid, text=enemy.data.get("phase_text", "")))
            if not enemy.charging:
                events.append(self._choose_intent(enemy))
        return events

    def _check_victory(self):
        if self.outcome is None and not self.alive_enemies():
            self.outcome = "victory"
            return [_event("victory", "Victory!")]
        return []

    # ----------------------------------------------------------- enemy turns
    def take_enemy_turn(self):
        if self.outcome:
            raise ValueError("battle is over")
        enemy = self.current
        if enemy is None or enemy.side != "enemy":
            raise ValueError("not an enemy's turn")
        attack = enemy.intent
        events = []
        if attack.get("charged") and not enemy.charging:
            enemy.charging = True
            events.append(_event("charge_start", f"{enemy.name} is charging {attack['name']}!",
                                 uid=enemy.uid, attack=attack, charging=True))
        else:
            events += self._resolve_attack(enemy, attack)
            enemy.charging = False
            enemy.last_was_charge = bool(attack.get("charged"))
            if self.outcome is None:
                events.append(self._choose_intent(enemy))
        events += self._advance()
        return events

    def _resolve_attack(self, enemy, attack):
        roll = self.rng.randint(attack["min_dmg"], attack["max_dmg"])
        events = []
        dealt = 0
        if self.guard_by is not None:
            events.append(_event("blocked", f"{enemy.name} used {attack['name']} on Leader: BLOCKED "
                                            f"(would be {roll})",
                                 uid=self.leader.uid, source=enemy.uid, attack=attack, roll=roll))
        elif self.ward > 0:
            self.ward -= 1
            events.append(_event("blocked", f"{enemy.name} used {attack['name']} on Leader: WARD blocks it "
                                            f"(would be {roll})",
                                 uid=self.leader.uid, source=enemy.uid, attack=attack, roll=roll, ward=True))
        else:
            dealt = roll
            self.leader_hp = max(0, self.leader_hp - roll)
            events.append(_event("damage", f"{enemy.name} used {attack['name']} on Leader: {roll} dmg "
                                           f"(HP {self.leader_hp}/{self.leader_max_hp})",
                                 uid=self.leader.uid, source=enemy.uid, amount=roll,
                                 hp=self.leader_hp, max_hp=self.leader_max_hp, attack=attack))

        heal = 0
        if attack.get("heal_self_pct"):
            heal += round(enemy.max_hp * attack["heal_self_pct"])
        if attack.get("lifesteal"):
            heal += dealt
        if heal:
            before = enemy.hp
            enemy.hp = min(enemy.max_hp, enemy.hp + heal)
            if enemy.hp > before:
                events.append(_event("enemy_heal", f"{enemy.name} recovers {enemy.hp - before} HP "
                                                   f"(HP {enemy.hp}/{enemy.max_hp})",
                                     uid=enemy.uid, amount=enemy.hp - before,
                                     hp=enemy.hp, max_hp=enemy.max_hp))

        if self.leader_hp <= 0:
            self.outcome = "defeat"
            events.append(_event("defeat", "The leader has fallen..."))
        return events

    def _choose_intent(self, enemy):
        options, weights = [], []
        for attack in enemy.data["attacks"]:
            if attack.get("charged") and not (enemy.is_boss and enemy.phase2 and not enemy.last_was_charge):
                continue
            weight = attack.get("phase2_weight", attack["weight"]) if enemy.phase2 else attack["weight"]
            if weight > 0:
                options.append(attack)
                weights.append(weight)
        enemy.intent = self.rng.choices(options, weights=weights)[0]
        return _event("intent", f"{enemy.name} prepares {enemy.intent['name']} "
                                f"({enemy.intent['min_dmg']}-{enemy.intent['max_dmg']})",
                      uid=enemy.uid, attack=enemy.intent, charging=enemy.charging)

    # ---------------------------------------------------------------- debug
    def debug_win(self):
        events = []
        for e in self.alive_enemies():
            e.hp = 0
            e.alive = False
            events.append(_event("death", f"[debug] {e.name} removed", uid=e.uid))
        events += self._check_victory()
        return events
