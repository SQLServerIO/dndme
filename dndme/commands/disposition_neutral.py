from dndme.commands import Command


class DispositionNeutral(Command):

    keywords = ['neutral']
    help_text = """{keyword}
{divider}
Summary: Mark one or more combatants as neutral in the player view.

Usage: {keyword} <target> [<target2> ...]

Example:

    {keyword} goblin
    {keyword} goblin1 goblin2 goblin3
"""

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        if not args:
            print("Need a combatant.")
            return

        target_names = args

        combat = self.game.combat

        for target_name in target_names:
            target = combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")

            target.disposition = "neutral"
            print(f"Okay; {target_name} is neutral in the player view.")

            self.game.changed = True
