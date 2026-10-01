from corruption import CorruptionState, StatusEffects


class GameData:
    def __init__(self):
        self.party = None
        self.corruption = CorruptionState(0.0)
        self.status = StatusEffects()
        self.level_index = 0
        self.pending_reward = None
        self.buffs_collected = 0

    def new_game(self, class_names, captain_index=0):
        from party import Party
        self.party = Party(class_names, captain_index)
        self.party.full_heal()
        self.corruption = CorruptionState(0.0)
        self.status = StatusEffects()
        self.level_index = 0
        self.buffs_collected = 0
