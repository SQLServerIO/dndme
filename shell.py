from attr import attrs, attrib
from dice import roll_dice, roll_dice_expr
from initiative import TurnManager
from loaders import EncounterLoader, MonsterLoader, PartyLoader
from math import inf, floor
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
import click
import glob
import pytoml as toml
import sys

default_encounters_dir = './encounters'
default_monsters_dir = './monsters'
default_party_file = 'party.toml'

commands = {}
manager = KeyBindingManager.for_prompt()
history = InMemoryHistory()
style = style_from_dict({
    Token.Toolbar: '#ffffff bg:#333333',
})


class DnDCompleter(Completer):
    """
    Simple autocompletion on a list of words.

    :param base_commands: List of base commands.
    :param ignore_case: If True, case-insensitive completion.
    :param meta_dict: Optional dict mapping words to their meta-information.
    :param WORD: When True, use WORD characters.
    :param sentence: When True, don't complete by comparing the word before the
        cursor, but by comparing all the text before the cursor. In this case,
        the list of words is just a list of strings, where each string can
        contain spaces. (Can not be used together with the WORD option.)
    :param match_middle: When True, match not only the start, but also in the
                         middle of the word.
    """
    def __init__(self, base_commands, ignore_case=False, meta_dict=None,
                 WORD=False, sentence=False, match_middle=False):
        assert not (WORD and sentence)

        self.base_commands = sorted(list(base_commands))
        self.ignore_case = ignore_case
        self.meta_dict = meta_dict or {}
        self.WORD = WORD
        self.sentence = sentence
        self.match_middle = match_middle

    def get_completions(self, document, complete_event):
        # Get word/text before cursor.
        if self.sentence:
            word_before_cursor = document.text_before_cursor
        else:
            word_before_cursor = document.get_word_before_cursor(
                    WORD=self.WORD)

        if self.ignore_case:
            word_before_cursor = word_before_cursor.lower()

        def word_matcher(word):
            """ True when the command before the cursor matches. """
            if self.ignore_case:
                word = word.lower()

            if self.match_middle:
                return word_before_cursor in word
            else:
                return word.startswith(word_before_cursor)

        suggestions = []
        document_text_list = document.text.split(' ')

        if len(document_text_list) < 2:
            suggestions = self.base_commands

        elif document_text_list[0] in self.base_commands:
            command = commands[document_text_list[0]]
            suggestions = command.get_suggestions(document_text_list) or []

        for word in suggestions:
            if word_matcher(word):
                display_meta = self.meta_dict.get(word, '')
                yield Completion(word, -len(word_before_cursor),
                                    display_meta=display_meta)


@attrs
class Combat:
    characters = attrib()

    @characters.default
    def _characters(self):
        return {}

    monsters = attrib()

    @monsters.default
    def _monsters(self):
        return {}

    defeated = attrib()

    @defeated.default
    def _defeated(self):
        return []

    tm = attrib(default=None)

    @property
    def combatant_names(self):
        return sorted(list(self.characters.keys()) +
                list(self.monsters.keys()))

    def get_target(self, name):
        return self.characters.get(name) or \
                self.monsters.get(name)


@attrs
class Game:
    encounters_dir = attrib(default=default_encounters_dir)
    monsters_dir = attrib(default=default_monsters_dir)
    party_file = attrib(default=default_party_file)

    stash = attrib(default={})
    combats = attrib(default=[])
    combat = attrib()

    @combat.default
    def _combat(self):
        combat = Combat()
        self.combats.append(combat)
        return combat

    @property
    def stashed_monster_names(self):
        return [k for k, v in self.stash.items() if hasattr(v, 'mtype')]

    @property
    def stashed_character_names(self):
        return [k for k, v in self.stash.items() if hasattr(v, 'cclass')]


def safe_input(text, default=None, converter=None):
    data = None

    while data is None:
        if default is not None:
            data = input(f"{text} [{default}]: ").strip()
        else:
            data = input(f"{text}: ").strip()

        if default and not data:
            data = default

        if converter:
            data = converter(data)

    return data


def convert_to_int(value):
    try:
        value = int(value)
    except ValueError:
        value = None
    return value


def convert_to_int_or_dice_expr(value):
    try:
        value = int(value)
    except ValueError:
        if 'd' in value:
            try:
                value = roll_dice_expr(value)
            except ValueError:
                value = None
        else:
            value = None
    return value


class Command:

    keywords = ['command']

    def __init__(self, game):
        self.game = game
        for kw in self.keywords:
            commands[kw] = self
        print("Registered "+self.__class__.__name__)

    def get_suggestions(self, words):
        return []

    def do_command(self, *args):
        print("Nothing happens.")

    def show_help_text(self, keyword):
        if hasattr(self, 'help_text'):
            divider = "-" * len(keyword)
            print(self.help_text.format(**locals()).strip())
        else:
            print(f"No help text available for: {keyword}")


class ListCommands(Command):

    keywords = ['commands']
    help_text = """{keyword}
{divider}
Summary: List available commands

Usage: {keyword}
"""

    def do_command(self, *args):
        print("Available commands:\n")
        for keyword in list(sorted(commands.keys())):
            print('*', keyword)


class Help(Command):

    keywords = ['help']
    help_text = """{keyword}
{divider}
Summary: Get help for a command.

Usage: {keyword} <command>
"""

    def get_suggestions(self, words):
        return list(sorted(commands.keys()))

    def do_command(self, *args):
        if not args:
            self.show_help_text('help')
            return

        keyword = args[0]
        command = commands.get(keyword)
        if not command:
            print(f"Unknown command: {keyword}")
            return
        command.show_help_text(keyword)

    def show_help_text(self, keyword):
        super().show_help_text(keyword)
        ListCommands.do_command(self, *[])


class Quit(Command):

    keywords = ['quit', 'exit']
    help_text = """{keyword}
{divider}
Summary: quit the shell

Usage: {keyword}
"""

    @manager.registry.add_binding(Keys.ControlD)
    def do_command(self, *args):
        print("Goodbye!")
        sys.exit(1)


class Roll(Command):

    keywords = ['roll', 'dice']
    help_text = """{keyword}
{divider}
Summary: Roll dice using a dice expression

Usage: {keyword} <dice expression> [<dice expression> ...]

Examples:

    {keyword} 3d6
    {keyword} 1d20+2
    {keyword} 2d4-1
    {keyword} 1d20 1d20
"""

    def do_command(self, *args):
        results = []
        for dice_expr in args:
            try:
                results.append(str(roll_dice_expr(dice_expr)))
            except ValueError:
                print(f"Invalid dice expression: {dice_expr}")
                return
        print(', '.join(results))


class Load(Command):

    keywords = ['load']
    help_text = """{keyword}
{divider}
Summary: Load stuff

Usage:
    {keyword} party
    {keyword} encounter
    {keyword} monster <monster>
"""

    def get_suggestions(self, words):
        if len(words) == 2:
            return ['encounter', 'monster', 'party']
        if len(words) == 3 and words[1] == 'monster':
            monster_loader = MonsterLoader(self.game.monsters_dir)
            return monster_loader.get_available_monster_keys()

    def do_command(self, *args):
        if not args:
            print("Load what?")
            return
        if args[0] == 'party':
            self.load_party()
        elif args[0] == 'encounter':
            self.load_encounter()
        elif args[0] == 'monster' and len(args) == 2:
            self.load_monster(args[-1])
        else:
            print("Sorry; can't load that.")

    def load_party(self):
        party_loader = PartyLoader(self.game.party_file)
        party = party_loader.load(self.game.combat)
        print("OK; loaded {} characters".format(len(party)))

    def load_encounter(self):

        def prompt_count(count, monster_name="monsters"):
            count = safe_input(
                    f"Number of {monster_name}",
                    default=count,
                    converter=convert_to_int_or_dice_expr)
            return count

        def prompt_initiative(monster):
            # prompt to add the monsters to initiative order
            roll_advice = f"1d20{monster.initiative_mod:+}" \
                    if monster.initiative_mod else "1d20"
            roll = safe_input(
                    f"Initiative for {monster.name}",
                    default=roll_advice,
                    converter=convert_to_int_or_dice_expr)
            print(f"Adding to turn order at: {roll}")
            return roll

        monster_loader = MonsterLoader(self.game.monsters_dir)
        encounter_loader = EncounterLoader(
                self.game.encounters_dir,
                monster_loader,
                count_resolver=prompt_count,
                initiative_resolver=prompt_initiative)

        encounters = encounter_loader.get_available_encounters()

        if not encounters:
            print("No available encounters found.")
            return

        # prompt to pick an encounter
        print("Available encounters:\n")
        for i, encounter in enumerate(encounters, 1):
            print(f"{i}: {encounter.name} ({encounter.location})")

        pick = input("\nLoad encounter: ")
        if not pick.isdigit():
            print("Invalid encounter.")
            return

        pick = int(pick) - 1
        if pick < 0 or pick > len(encounters):
            print("Invalid encounter.")
            return

        encounter = encounters[pick]
        monsters = encounter_loader.load(encounter, self.game.combat)
        print(f"Loaded encounter: {encounter.name}"
                f" with {len(monsters)} monsters")

    def load_monster(self, monster_name):

        def prompt_initiative(monster):
            # prompt to add the monsters to initiative order
            roll_advice = f"1d20{monster.initiative_mod:+}" \
                    if monster.initiative_mod else "1d20"
            roll = safe_input(
                    f"Initiative for {monster.name}",
                    default=roll_advice,
                    converter=convert_to_int_or_dice_expr)
            print(f"Adding to turn order at: {roll}")
            return roll

        monster_loader = MonsterLoader(self.game.monsters_dir)
        count = safe_input(
                "Number of monsters",
                converter=convert_to_int_or_dice_expr)
        monsters = monster_loader.load(monster_name, count=count)

        #TODO: this is a cheat and really bad and we should clean it up
        encounter_loader = EncounterLoader(
                self.game.encounters_dir,
                monster_loader,
                initiative_resolver=prompt_initiative)
        encounter_loader._set_hp([], monsters)
        encounter_loader._set_names([], monsters)
        encounter_loader._add_to_combat(self.game.combat, monsters)
        for monster in monsters:
            monster.origin = "unplanned"


class Show(Command):

    keywords = ['show']

    def get_suggestions(self, words):
        if len(words) == 2:
            return ['monsters', 'party', 'stash', 'defeated', 'turn',
                    'initiative', 'order', 'turns', 'combats']

    def do_command(self, *args):
        if not args:
            print("Show what?")
            return
        if args[0] == 'party':
            self.show_party()
        elif args[0] == 'monsters':
            self.show_monsters()
        elif args[0] == 'stash':
            self.show_stash()
        elif args[0] == 'defeated':
            self.show_defeated()
        elif args[0] == 'turn':
            self.show_turn()
        elif args[0] in ('initiative', 'order', 'turns'):
            self.show_turns()
        elif args[0] == 'combats':
            self.show_combats()
        else:
            print("Sorry; can't show that.")

    def show_party(self):
        combat = self.game.combat
        party = list(sorted(combat.characters.items()))
        for name, character in party:
            print(f"{name:20}"
                    f"\tHP: {character.cur_hp:0>2}/{character.max_hp:0>2}"
                    f"\tAC: {character.ac:0>2}"
                    f"\tPer: {character.senses['perception']:0>2}"
            )
            if character.conditions:
                conds = ', '.join([f"{x}:{y}"
                        if y != inf else x
                        for x, y in character.conditions.items()])
                print(f"    Conditions: {conds}")

    def show_monsters(self):
        combat = self.game.combat
        monsters = list(sorted(combat.monsters.items()))
        for name, monster in monsters:
            print(f"{name:20}"
                    f"\tHP: {monster.cur_hp:0>2}/{monster.max_hp:0>2}"
                    f"\tAC: {monster.ac:0>2}"
                    f"\tPer: {monster.senses['perception']:0>2}"
            )
            if monster.conditions:
                conds = ', '.join([f"{x}:{y}"
                        if y != inf else x
                        for x, y in monster.conditions.items()])
                print(f"    Conditions: {conds}")

    def show_stash(self):
        if not self.game.stash:
            print("No combatants stashed.")
            return

        for combatant in self.game.stash.values():
            if hasattr(combatant, 'origin'):
                print(f"{combatant.name:20} {combatant.origin:.50}")
            else:
                print(f"{combatant.name:20} (party)")

    def show_defeated(self):
        combat = self.game.combat

        total_xp = 0
        for monster in combat.defeated:
            total_xp += monster.xp
            print(f"{monster.name:20} {monster.origin:.40}\tXP: {monster.xp}")

        if not combat.characters:
            print(f"Total XP: {total_xp}")
        else:
            divided_xp = floor(total_xp / len(combat.characters))
            print(f"Total XP: {total_xp} ({divided_xp} each)")

    def show_turn(self):
        combat = self.game.combat
        if not combat.tm:
            print("No turn in progress.")
            return
        elif not combat.tm.cur_turn:
            print("No turn in progress.")
            return
        turn = combat.tm.cur_turn
        print(f"Round: {turn[0]} Initiative: {turn[1]} Name: {turn[2].name}")

    def show_turns(self):
        combat = self.game.combat
        if not combat.tm:
            print("No turn in progress.")
            return
        for roll, combatants in combat.tm.turn_order:
            print(f"{roll}: {', '.join([x.name for x in combatants])}")

    def show_combats(self):
        for i, combat in enumerate(self.game.combats, 1):
            print(f"{i}: {', '.join([x for x in combat.characters])}")


class Start(Command):

    keywords = ['start']

    def do_command(self, *args):
        combat = self.game.combat

        combat.tm = TurnManager()

        print("Enter initiative rolls or press enter to 'roll' automatically.")
        for monster in combat.monsters.values():
            roll_advice = f"1d20{monster.initiative_mod:+}" \
                    if monster.initiative_mod else "1d20"
            roll = safe_input(
                    f"Initiative for {monster.name}",
                    default=roll_advice,
                    converter=convert_to_int_or_dice_expr)
            combat.tm.add_combatant(monster, roll)
            print(f"Added to turn order in {roll}\n")

        for character in combat.characters.values():
            roll_advice = f"1d20{character.initiative_mod:+}" \
                    if character.initiative_mod else "1d20"
            roll = safe_input(
                    f"Initiative for {character.name}",
                    default=roll_advice,
                    converter=convert_to_int_or_dice_expr)
            combat.tm.add_combatant(character, roll)
            print(f"Added to turn order in {roll}\n")

        print("\nBeginning combat with: ")
        for roll, combatants in combat.tm.turn_order:
            print(f"{roll}: {', '.join([x.name for x in combatants])}")

        combat.tm.turns = combat.tm.generate_turns()


class End(Command):

    keywords = ['end']

    def do_command(self, *args):
        combat = self.game.combat
        if not combat.tm:
            print("Combat hasn't started yet.")
            return

        cur_turn = combat.tm.cur_turn

        combat.tm = None
        Show.show_defeated(self)
        combat.defeated = []
        combat.monsters = {}

        if cur_turn:
            rounds = cur_turn[0]
            duration_sec = cur_turn[0] * 6
        else:
            rounds = 0
            duration_sec = 0

        if duration_sec > 60:
            duration = f"{duration_sec // 60} min {duration_sec % 60} sec"
        else:
            duration = f"{duration_sec} sec"

        print(f"Combat ended in {rounds} rounds ({duration})")


class NextTurn(Command):

    keywords = ['next']

    def do_command(self, *args):
        combat = self.game.combat
        if not combat.tm:
            print("Combat hasn't started yet.")
            return

        num_turns = int(args[0]) if args else 1

        for i in range(num_turns):
            turn = combat.tm.cur_turn
            if turn:
                combatant = turn[-1]
                conditions_removed = combatant.decrement_condition_durations()
                if conditions_removed:
                    print(f"{combatant.name} conditions removed: "
                            f"{', '.join(conditions_removed)}")

            turn = next(combat.tm.turns)
            combat.tm.cur_turn = turn
            Show.show_turn(self)


class Damage(Command):

    keywords = ['damage', 'hurt', 'hit']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        if len(args) < 2:
            print("Need a target and an amount of HP.")
            return

        target_names = args[0:-1]
        try:
            amount = int(args[-1])
        except ValueError:
            print("Need an amount of HP.")
            return

        combat = self.game.combat

        for target_name in target_names:

            target = combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            target.cur_hp -= amount
            print(f"Okay; damaged {target_name}. "
                    f"Now: {target.cur_hp}/{target.max_hp}")

            if target_name in combat.monsters and target.cur_hp == 0:
                if (input(f"{target_name} reduced to 0 HP--"
                        "mark as defeated? [Y]: ")
                        or 'y').lower() != 'y':
                    continue
                DefeatMonster.do_command(self, target_name)


class Heal(Command):

    keywords = ['heal']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        if len(args) < 2:
            print("Need a target and an amount of HP.")
            return

        target_names = args[0:-1]
        try:
            amount = int(args[-1])
        except ValueError:
            print("Need an amount of HP.")
            return

        if len(args) < 2:
            print("Need a target and an amount of HP.")
            return

        combat = self.game.combat

        for target_name in target_names:
            target = combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            if 'dead' in target.conditions:
                print(f"Cannot heal {target_name} (dead)")
                continue

            target.cur_hp += amount
            print(f"Okay; healed {target_name}. "
                    f"Now: {target.cur_hp}/{target.max_hp}")


class CastSpell(Command):

    keywords = ['cast']
    help_text = """{keyword}
{divider}
Summary: Make a combatant cast a spell at a particular spell level. By default
selects the current combatant, but the caster may be explicitly specified in
(for example) cases where spells might be cast as reactions.

Usage: {keyword} <spell level>
       {keyword> <spell level> <caster>

Example: {keyword} 2
         {keyword} evil_wizard 2
"""

    def get_suggestions(self, words):
        combat = self.game.combat

        if len(words) < 2:
            return []

        if len(words) >= 2:
            caster = self._get_caster(words[1])

            if not caster:
                return sorted(set(combat.combatant_names))

            elif not (caster.features.get('spellcasting')):
                return []

            else:
                slots = caster.features['spellcasting']['slots']
                slots_used = caster.features['spellcasting']['slots_used']
                return [str(i+1) for i in range(len(slots))
                        if slots_used[i] < slots[i]]

    def _get_caster(self, name):
        combat = self.game.combat
        caster = None

        if name:
            caster = combat.get_target(name)

        if not caster:
            if combat.tm and combat.tm.cur_turn and not name:
                caster = combat.tm.cur_turn[-1]

        return caster

    def do_command(self, *args):
        if not args:
            print("Need a caster or a spell level.")
            return

        # Get the caster...
        caster_name = args[0] if not args[0].isdigit() else None
        caster = self._get_caster(caster_name)

        if not caster:
            print(f"No caster identified.")
            return

        if 'spellcasting' not in caster.features:
            print("Combatant can't cast spells.")
            return

        # Determine the spell level being cast
        try:
            spell_level = int(args[-1]) - 1
        except ValueError:
            print("Invalid spell level.")
            return

        if spell_level < 0:
            print("Can't cast spells at spell level 0.")
            return

        # And cast it!
        spells = caster.features['spellcasting']['spells']
        slots = caster.features['spellcasting']['slots']
        slots_used = caster.features['spellcasting']['slots_used']

        try:
            if slots_used[spell_level] < slots[spell_level]:
                slots_used[spell_level] += 1
                remaining = slots[spell_level] - slots_used[spell_level]
                print(f"Okay; {remaining} level {spell_level+1} slots left.")
            else:
                print("Combatant has no available spell slots at that level.")
                return
        except IndexError:
            print("Combatant can't cast spells of that level.")
            return


class Swap(Command):

    keywords = ['swap']
    help_text = """{keyword}
{divider}
Summary: Swap two combatants in turn order.

Usage: {keyword} <combatant1> <combatant2>
"""

    def get_suggestions(self, words):
        combat = self.game.combat
        if len(words) in (2, 3):
            return combat.combatant_names

    def do_command(self, *args):
        if len(args) != 2:
            print("Need two combatants to swap.")
            return

        name1 = args[0]
        name2 = args[1]

        combat = self.game.combat

        combatant1 = combat.get_target(name1)
        combatant2 = combat.get_target(name2)

        if not combatant1:
            print(f"Invalid target: {name1}")
            return

        if not combatant2:
            print(f"Invalid target: {name2}")
            return

        combat.tm.swap(combatant1, combatant2)
        print(f"Okay; swapped {name1} and {name2}.")


class Move(Command):

    keywords = ['move']
    help_text = """{keyword}
{divider}
Summary: Move a combatant to a different initiative value.

Usage: {keyword} <combatant> <initiative>
"""

    def get_suggestions(self, words):
        if len(words) == 2:
            combat = self.game.combat
            return combat.combatant_names

    def do_command(self, *args):
        if len(args) != 2:
            print("Need a combatant and an initiative value.")
            return

        combat = self.game.combat

        name = args[0]
        target = combat.get_target(name)

        if not target:
            print(f"Invalid target: {name}")
            return

        try:
            new_initiative = int(args[1])
        except ValueError:
            print("Invalid initiative value")
            return

        combat.tm.move(target, new_initiative)
        print(f"Okay; moved {name} to {new_initiative}.")


class Reorder(Command):

    keywords = ['reorder']
    help_text = """{keyword}
{divider}
Summary: Reorder the combatants with a particular initiative value.

Usage: reorder <initiative value> <combatant1> [<combatant2> ...]
"""

    def get_suggestions(self, words):
        combat = self.game.combat

        if len(words) > 2:
            try:
                initiative_value = int(words[1])
            except ValueError:
                return []

            combatant_names = [x.name for x in
                    combat.tm.initiative[initiative_value]]
            names_already_chosen = words[2:]
            return list(set(combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        if len(args) < 2:
            print("Need an initiative and combatants to reorder.")
            return

        combat = self.game.combat

        if not combat.tm:
            print("No encounter in progress.")
            return

        try:
            i = int(args[0])
        except ValueError:
            print("Invalid initiative value")
            return

        names = args[1:]
        old_initiative = combat.tm.initiative[i]
        new_initiative = [combat.get_target(x) for x in names]

        if set(names) != set([x.name for x in new_initiative if x]):
            print("Could not reorder: couldn't find all combatants specified.")
            return

        elif set(names) != set([x.name for x in old_initiative]):
            print("Could not reorder: not all original combatants specified.")
            return

        combat.tm.initiative[i] = new_initiative
        print(f"Okay; updated {i}: "
                f"{', '.join([x.name for x in combat.tm.initiative[i]])}")


class SetCondition(Command):

    keywords = ['set']
    help_text = """{keyword}
{divider}
Summary: Set a condition on a target, optionally for a duration

Usage: {keyword} <target> <condition> [<duration> [<units>]]

Examples:

    {keyword} Frodo prone
    {keyword} Aragorn smolder 3
    {keyword} Gandalf concentrating 1 minute
    {keyword} Gollum lucid 5 minutes
"""
    conditions = [
        'blinded',
        'charmed',
        'concentrating',
        'deafened',
        'dead',
        'exhausted',
        'frightened',
        'grappled',
        'incapacitated',
        'invisible',
        'paralyzed',
        'petrified',
        'poisoned',
        'prone',
        'restrained',
        'stunned',
        'unconscious',
    ]

    multipliers = {
        'turn': 1,
        'turns': 1,
        'round': 1,
        'rounds': 1,
        'minute': 10,
        'minutes': 10,
        'min': 10,
    }

    def get_suggestions(self, words):
        combat = self.game.combat
        if len(words) == 2:
            return combat.combatant_names
        elif len(words) == 3:
            return self.conditions
        elif len(words) == 5:
            return sorted(self.multipliers.keys())

    def do_command(self, *args):
        if len(args) < 2:
            print("Need a combatant and condition.")
            return

        target_name = args[0]
        condition = args[1]
        duration = inf

        if len(args) >= 3:
            duration = int(args[2])

        if len(args) >= 4:
            units = args[3]
            duration *= self.multipliers.get(units, 1)

        combat = self.game.combat

        target = combat.get_target(target_name)
        if not target:
            print(f"Invalid target: {target_name}")
            return

        if hasattr(target, 'immune') and condition in target.immune:
            print(f"Cannot set condition '{condition}' on {target_name};"
                    " target is immune.")
            return

        target.set_condition(condition, duration=duration)
        print(f"Okay; set condition '{condition}' on {target_name}.")


class UnsetCondition(Command):

    keywords = ['unset']
    help_text = """{keyword}
{divider}
Summary: Remove a condition from a target

Usage: {keyword} <target> <condition>

Examples:

    {keyword} Frodo prone
"""

    def get_suggestions(self, words):
        combat = self.game.combat
        if len(words) == 2:
            return combat.combatant_names
        elif len(words) == 3:
            target_name = words[1]
            target = combat.get_target(target_name)
            if not target:
                return []
            return list(sorted(target.conditions.keys()))

    def do_command(self, *args):
        if len(args) < 2:
            print("Need a combatant and a condition.")
            return

        target_name = args[0]
        condition = args[1]

        combat = self.game.combat

        target = combat.get_target(target_name)
        if not target:
            print(f"Invalid target: {target_name}")
            return

        target.unset_condition(condition)
        print(f"Okay; removed condition '{condition}' from {target_name}.")


class StashCombatant(Command):

    keywords = ['stash']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        combat = self.game.combat

        for target_name in args:
            target = combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            if combat.tm:
                combat.tm.remove_combatant(target)
            if target_name in combat.monsters:
                combat.monsters.pop(target_name)
            else:
                combat.characters.pop(target_name)

            self.game.stash[target_name] = target
            print(f"Stashed {target_name}")


class UnstashCombatant(Command):

    keywords = ['unstash']

    def get_suggestions(self, words):
        names_already_chosen = words[1:]
        return sorted(set(self.game.stash.keys()) - set(names_already_chosen))

    def do_command(self, *args):
        combat = self.game.combat

        for target_name in args:
            if target_name not in self.game.stash:
                print(f"Invalid target: {target_name}")
                continue

            target = self.game.stash.pop(target_name)

            if hasattr(target, 'mtype'):
                combat.monsters[target_name] = target
            else:
                combat.characters[target_name] = target

            print(f"Unstashed {target_name}")

            if combat.tm:
                roll_advice = f"1d20{target.initiative_mod:+}" \
                        if target.initiative_mod else "1d20"
                roll = safe_input(
                        f"Initiative for {target.name}",
                        default=roll_advice,
                        converter=convert_to_int_or_dice_expr)
                combat.tm.add_combatant(target, roll)
                print(f"Added to turn order in {roll}")


class DefeatMonster(Command):

    keywords = ['defeat']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.monsters.keys()) - set(names_already_chosen))

    def do_command(self, *args):
        combat = self.game.combat
        for target_name in args:
            target = combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            if combat.tm:
                combat.tm.remove_combatant(target)
            combat.monsters.pop(target_name)
            combat.defeated.append(target)
            print(f"Defeated {target_name}")


class RemoveCombatant(Command):

    keywords = ['remove']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(
                list(combat.monsters.keys()) +
                list(self.game.stashed_monster_names)) -
                set(names_already_chosen))

    def do_command(self, *args):
        combat = self.game.combat

        for target_name in args:
            target = combat.get_target(target_name)
            if target and hasattr(target, 'mytpe'):
                if combat.tm:
                    combat.tm.remove_combatant(target)
                combat.monsters.pop(target_name)
                print(f"Removed {target_name}")
            elif target_name in self.game.stash and \
                    hasattr(self.game.stash[target_name], 'mtype'):
                self.game.stash.pop(target_name)
                print(f"Removed {target_name} from stash")
            else:
                print(f"Invalid target: {target_name}")
                continue


class SplitCombat(Command):

    keywords = ['split']

    def get_suggestions(self, words):
        combat = self.game.combat
        names_already_chosen = words[1:]
        return sorted(set(combat.combatant_names) - set(names_already_chosen))

    def do_command(self, *args):
        source_combat = self.game.combat
        dest_combat = Combat()
        self.game.combats.append(dest_combat)

        if not len(args):
            print("Okay; created new combat")
            return

        for target_name in args:
            target = source_combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            if source_combat.tm:
                source_combat.tm.remove_combatant(target)
            if hasattr(target, 'mtype'):
                source_combat.monsters.pop(target_name)
                dest_combat.monsters[target_name] = target
            else:
                source_combat.characters.pop(target_name)
                dest_combat.characters[target_name] = target

        print("Okay; created new combat with "
                f"{', '.join(dest_combat.combatant_names)}")


class SwitchCombat(Command):

    keywords = ['switch']

    def get_suggestions(self, words):
        if len(words) == 2:
            return [f"{i} - {', '.join([x for x in combat.characters])}"
                    for i, combat in enumerate(self.game.combats, 1)]

    def do_command(self, *args):
        switch_to = int(args[0]) if args else None
        if switch_to and 1 <= switch_to <= len(self.game.combats):
            switch_to -= 1
            self.game.combat = self.game.combats[switch_to]
        else:
            switch_to = self.game.combats.index(self.game.combat) + 1
            if switch_to >= len(self.game.combats):
                switch_to = 0
            self.game.combat = self.game.combats[switch_to]

        print(f"Okay; switched to combat {switch_to + 1}")
        Show.show_party(self)


class JoinCombat(Command):

    keywords = ['join']

    def get_suggestions(self, words):
        if len(words) == 2:
            return [f"{i} - {', '.join([x for x in combat.characters])}"
                    for i, combat in enumerate(self.game.combats, 1)]

        elif len(words) > 2:
            names_already_chosen = words[2:]
            combat = self.game.combat
            return sorted(set(combat.combatant_names) - \
                    set(names_already_chosen))

    def do_command(self, *args):
        source_combat = self.game.combat

        if not args:
            print("Join which combat group?")
            return

        try:
            join_to = int(args[0]) - 1
        except ValueError:
            print("Invalid combat to join to.")
            return

        dest_combat = self.game.combats[join_to]

        if len(args) == 1:
            # join all to dest
            target_names = list(source_combat.characters.keys())
        else:
            # join specific characters to dest
            target_names = args[1:]

        if source_combat.defeated:
            print("Monsters were defeated:\n")
            Show.show_defeated(self)

        for target_name in target_names:
            target = source_combat.get_target(target_name)
            if not target:
                print(f"Invalid target: {target_name}")
                continue

            if source_combat.tm:
                source_combat.tm.remove_combatant(target)

            if hasattr(target, 'mtype'):
                source_combat.monsters.pop(target_name)
                dest_combat.monsters[target_name] = target
            else:
                source_combat.characters.pop(target_name)
                dest_combat.characters[target_name] = target

        if source_combat.monsters and not source_combat.characters:
            print("Monsters remain, stashing them:\n")
            StashCombatant.do_command(self,
                    *list(source_combat.monsters.keys()))

        if not source_combat.characters and not source_combat.monsters:
            print("Combat group is empty; switching...")
            SwitchCombat.do_command(self)
            self.game.combats.remove(source_combat)


class CombatantDetails(Command):

    keywords = ['details']

    def mod_fmt(self, modifier):
        return f"+{modifier}" if modifier > -1 else f"{modifier}"

    def get_suggestions(self, words):
        combat = self.game.combat

        if len(words) == 2:
            return sorted(set(combat.combatant_names))

    def do_command(self, *args):
        combat = self.game.combat

        if args:
            target = combat.get_target(args[0])
        else:
            if not combat.tm or not combat.tm.cur_turn:
                print("No target specified.")
                return
            target = combat.tm.cur_turn[-1]

        t = target

        if hasattr(target, 'cclass'):
            print(f"{t.name}: Level {t.level} {t.race} {t.cclass}")
            print(f"AC: {t.ac} HP: {t.cur_hp}/{t.max_hp}")
            print(', '.join([f"{x}: {y}"
                    for x, y in t.senses.items()]))

            if t.conditions:
                conds = ', '.join([f"{x}:{y}"
                        if y != inf else x
                        for x, y in t.conditions.items()])
                print(f"Conditions: {conds}")

        else:
            mf = self.mod_fmt

            print()
            print(f"{t.name}: {t.race} - {t.size} {t.mtype}, {t.alignment}")
            print(f"AC: {t.ac} ({t.armor or None}) HP: {t.cur_hp}/{t.max_hp}")
            print(f"Speed: {t.speed}")
            print(f"STR: {t.str} ({mf(t.str_mod)}) "
                    f"DEX: {t.dex} ({mf(t.dex_mod)}) "
                    f"CON: {t.con} ({mf(t.con_mod)}) "
                    f"INT: {t.int} ({mf(t.int_mod)}) "
                    f"WIS: {t.wis} ({mf(t.wis_mod)}) "
                    f"CHA: {t.cha} ({mf(t.cha_mod)})")

            if t.senses:
                print("Senses: " + \
                        ', '.join([f"{x}: {y}"
                                for x, y in t.senses.items()]))
            if t.skills:
                print("Skills: " + \
                        ', '.join([f"{x}: {y}"
                                for x, y in t.skills.items()]))
            if t.immune:
                print(f"Immune: {', '.join(t.immune)}")
            if t.resist:
                print(f"Resist: {', '.join(t.resist)}")
            if t.vulnerable:
                print(f"Vulnerable: {', '.join(t.vulnerable)}")
            if t.languages:
                print(f"Languages: {', '.join(t.languages)}")

            if t.conditions:
                conds = ', '.join([f"{x}:{y}"
                        if y != inf else x
                        for x, y in t.conditions.items()])
                print(f"Conditions: {conds}")

            print()

            if t.features:
                print("Features")
                print("--------")

                for k, s in t.features.items():
                    print(f"{s['name']}\n{s['description'].strip()}")

                    if k == 'spellcasting':
                        print(f"Cantrips: {', '.join(s['cantrips'])}")
                        print(f"Spells: ")
                        for i, spells in enumerate(s['spells']):
                            print(f"Level {i+1} "
                                    f"({s['slots_used'][i]}/{s['slots'][i]}): "
                                    f"{', '.join(spells)}")
                    print()

            if t.actions:
                print("Actions")
                print("-------")
                for a in t.actions.values():
                    print(a['name'])
                    print(a['description'].strip())
                    print()

            if t.legendary_actions:
                print("Legendary Actions")
                print("-----------------")
                for a in t.legendary_actions.values():
                    print(a['name'])
                    print(a['description'].strip())
                    print()

            if t.reactions:
                print("Reactions")
                print("---------")
                for r in t.reactions.values():
                    print(r['name'])
                    print(r['description'].strip())
                    print()

            print(t.notes.strip())


def register_commands(game):
    ListCommands(game)
    Help(game)
    Quit(game)
    Load(game)
    Show(game)
    Start(game)
    NextTurn(game)
    End(game)
    Damage(game)
    Heal(game)
    CastSpell(game)
    Swap(game)
    Move(game)
    Reorder(game)
    Roll(game)
    SetCondition(game)
    UnsetCondition(game)
    StashCombatant(game)
    UnstashCombatant(game)
    DefeatMonster(game)
    RemoveCombatant(game)
    SplitCombat(game)
    SwitchCombat(game)
    JoinCombat(game)
    CombatantDetails(game)


def get_bottom_toolbar_tokens(cli):
    return [(Token.Toolbar, 'Exit:Ctrl+D ')]


@click.command()
@click.option('--encounters', default='./encounters',
        help="Directory containing encounters TOML files; "
            f"default: {default_encounters_dir}")
@click.option('--monsters', default='./monsters',
        help="Directory containing monsters TOML files; "
            f"default: {default_monsters_dir}")
@click.option('--party', default='party.toml',
        help="Player character party TOML file to use; "
            f"default: {default_party_file}")
def main_loop(encounters, monsters, party):
    game = Game(encounters_dir=encounters, monsters_dir=monsters,
            party_file=party)
    register_commands(game)

    while True:
        try:
            user_input = prompt("> ",
                completer=DnDCompleter(base_commands=commands.keys(),
                        ignore_case=True),
                history=history,
                get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                key_bindings_registry=manager.registry,
                style=style).split()
            if not user_input:
                continue

            command = commands.get(user_input[0]) or None
            if not command:
                print("Unknown command.")
                continue

            command.do_command(*user_input[1:])
            print()
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == '__main__':
    main_loop()
