from settings import clamp

STATUS_DURATION = 4.0


class CorruptionState:
    """Global corruption meter, shared across overworld and battle."""

    def __init__(self, value=0.0):
        self.value = value

    def add(self, amount):
        self.value = clamp(self.value + amount, 0, 100)

    @property
    def is_critical(self):
        return self.value >= 100


class StatusEffects:
    """Per-player status timers: slow, weak_jump, drain. Minecraft-style stacking refresh."""

    def __init__(self):
        self.timers = {}

    def apply_corruption_touch(self):
        for key in ("slow", "weak_jump", "drain"):
            self.timers[key] = STATUS_DURATION

    def update(self, dt, on_drain_tick=None):
        expired = []
        for key in list(self.timers.keys()):
            self.timers[key] -= dt
            if self.timers[key] <= 0:
                expired.append(key)
        for key in expired:
            del self.timers[key]
        if "drain" in self.timers and on_drain_tick:
            on_drain_tick(dt)

    @property
    def speed_mult(self):
        return 0.55 if "slow" in self.timers else 1.0

    @property
    def jump_mult(self):
        return 0.65 if "weak_jump" in self.timers else 1.0

    @property
    def active(self):
        return self.timers
