from collections import defaultdict


class TurnManager:

    """
    Manage turns by initiative within a round of combat.

    Example usage:

    >>> tm = TurnManager()
    >>> tm.add_combatant("Gandalf", 11)
    >>> tm.add_combatant("Bilbo", 17)
    >>> tm.add_combatant("Smaug", 15)
    >>> turns = tm.generate_turns()
    >>> next(turns)
    (1, 17, "Bilbo")
    >>> next(turns)
    (1, 15, "Smaug")
    >>> next(turns)
    (1, 11, "Gandalf")
    >>> next(turns)
    (2, 17, "Bilbo")
    >>> tm.remove_combatant("Smaug")
    """

    def __init__(self):
        self.initiative = defaultdict(list)
        self.round_number = 0

    def add_combatant(self, combatant, initiative_roll):
        for combatants in self.initiative.values():
            if combatant in combatants:
                raise Exception("Combatants must be unique")
        self.initiative[initiative_roll].append(combatant)

    def remove_combatant(self, combatant):
        for combatants in self.initiative.values():
            if combatant in combatants:
                combatants.remove(combatant)
                return combatant
        raise Exception("Combatant not found")

    def generate_turns(self):
        while self.initiative:
            self.round_number += 1
            turn_order = list(reversed(sorted(self.initiative.items())))
            for turn, combatants in turn_order:
                for combatant in combatants:
                    yield self.round_number, turn, combatant

