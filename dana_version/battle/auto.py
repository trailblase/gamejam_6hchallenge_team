"""Automatic party-turn policy for the battle engine.

This module is deliberately presentation-free: it chooses valid engine
actions from the current battle state and never mutates that state itself.
"""


def _expected_damage(member, multiplier):
    return member.atk * multiplier


def _target_priority(state, member, multiplier=1.0):
    """Prefer immediate kills, then imminent/high-damage enemy threats."""
    order = {uid: index for index, uid in enumerate(state.timeline())}

    def score(enemy):
        intent = enemy.intent or {}
        lethal = enemy.hp <= _expected_damage(member, multiplier)
        # Killing an enemy before its turn is the strongest defensive action.
        return (
            0 if lethal else 1,
            order.get(enemy.uid, 99),
            -intent.get("max_dmg", 0),
            enemy.hp / max(1, enemy.max_hp),
            0 if enemy.is_boss else 1,
        )

    return min(state.alive_enemies(), key=score)


def _should_guard_lethal_hit(state, member):
    """Guard when a lethal enemy attack lands before this member acts again."""
    if state.guard_by is not None:
        return False

    future = state.predict(max(12, len(state.units()) * 2))
    next_member_turn = next((i for i, uid in enumerate(future) if uid == member.uid), len(future))
    imminent = set(future[:next_member_turn])
    return any(
        enemy.uid in imminent
        and enemy.intent
        and enemy.intent["max_dmg"] >= state.leader_hp
        for enemy in state.alive_enemies()
    )


def choose_action(state):
    """Return the automatic action for the current party member.

    The policy heals a meaningfully injured leader, uses multi-target attacks
    when they outperform a basic attack, and otherwise spends available SP on
    stronger single-target skills. Target selection focuses imminent threats
    and takes free kills when possible.
    """
    member = state.current
    if member is None or member.side != "party":
        raise ValueError("auto policy requires a party member's turn")

    enemies = state.alive_enemies()
    if not enemies:
        raise ValueError("auto policy requires at least one living enemy")

    if _should_guard_lethal_hit(state, member):
        return {"kind": "block"}

    skill = member.char["skill"]
    skill_ready, _ = state.skill_status(member)

    if skill_ready and skill["effect"] == "heal_leader":
        missing_hp = state.leader_max_hp - state.leader_hp
        if missing_hp >= max(10, skill["amount"] * 0.65):
            return {"kind": "skill"}

    if skill_ready and skill["effect"] == "aoe_damage" and len(enemies) >= 2:
        # Cleave's combined damage is better than one basic attack for 2+ foes.
        return {"kind": "skill"}

    if skill_ready and skill["effect"] == "single_damage":
        target = _target_priority(state, member, skill["multiplier"])
        return {"kind": "skill", "target": target.uid}

    target = _target_priority(state, member, member.char["basic_attack"]["multiplier"])
    return {"kind": "attack", "target": target.uid}


def choose_reward(rewards, run):
    """Pick a useful quick-battle reward, valuing recovery when HP is low."""
    missing_hp = max(0, run.leader_max_hp - run.leader_hp)

    def score(reward):
        effect, value = reward["effect"], reward["value"]
        if effect == "heal":
            return min(value, missing_hp) * 0.9
        if effect == "leader_max_hp":
            return 7 + min(value, missing_hp) * 0.9
        if effect == "atk_pct":
            return 12
        if effect == "max_sp":
            return 7
        if effect == "spd":
            return 6
        return 0

    return max(rewards, key=score)
