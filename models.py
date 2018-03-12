from attr import attrs, attrib
from attr import Factory as attr_factory
from math import floor, inf
import dice


@attrs
class Combatant:
    name = attrib(default="")
    race = attrib(default="")
    initiative_mod = attrib(default=0)
    ac = attrib(default=0)

    senses = attrib(default=attr_factory(dict))
    conditions = attrib(default=attr_factory(dict))

    _max_hp = attrib(default=10)
    _cur_hp = attrib(default=10)

    @property
    def max_hp(self):
        return self._max_hp

    @max_hp.setter
    def max_hp(self, value):
        try:
            self._max_hp = int(value)
        except ValueError:
            # we have an expression for max hp, so roll it
            self._max_hp = dice.roll_dice_expr(value)
        # setting max_hp for the first time? we should set cur_hp too
        if self.cur_hp is None:
            self.cur_hp = self._max_hp

    @property
    def cur_hp(self):
        return self._cur_hp

    @cur_hp.setter
    def cur_hp(self, value):
        if value > self.max_hp:
            value = self.max_hp
        if value < 0:
            if abs(value) >= self.max_hp:
                self.conditions = {'dead': inf}
            value = 0
        self._cur_hp = value

    def set_condition(self, condition, duration=inf):
        self.conditions[condition] = duration

    def unset_condition(self, condition):
        try:
            self.conditions.pop(condition)
        except KeyError:
            # We can probably safely ignore failures here,
            # since it shouldn't be the end of the world
            # to remove a condition that isn't in effect.
            pass

    def decrement_condition_durations(self):
        conditions_removed = []

        for condition in list(self.conditions):
            self.conditions[condition] -= 1

            if self.conditions[condition] == 0:
                self.conditions.pop(condition)
                conditions_removed.append(condition)

        return conditions_removed


@attrs
class Character(Combatant):
    cclass = attrib(default="Fighter")
    level = attrib(default=1)


@attrs
class Monster(Combatant):
    cr = attrib(default=0)
    xp = attrib(default=0)
    size = attrib(default="medium")
    mtype = attrib(default="humanoid")
    alignment = attrib(default="unaligned")

    str = attrib(default=10)
    dex = attrib(default=10)
    con = attrib(default=10)
    int = attrib(default=10)
    wis = attrib(default=10)
    cha = attrib(default=10)

    @property
    def str_mod(self):
        return self.ability_modifier(self.str)

    @str_mod.setter
    def str_mod(self, x):
        pass

    @property
    def dex_mod(self):
        return self.ability_modifier(self.dex)

    @dex_mod.setter
    def dex_mod(self, x):
        pass

    @property
    def initiative_mod(self):
        return self.ability_modifier(self.dex)

    @initiative_mod.setter
    def initiative_mod(self, x):
        pass

    @property
    def con_mod(self):
        return self.ability_modifier(self.con)

    @con_mod.setter
    def con_mod(self, x):
        pass

    @property
    def int_mod(self):
        return self.ability_modifier(self.int)

    @int_mod.setter
    def int_mod(self, x):
        pass

    @property
    def wis_mod(self):
        return self.ability_modifier(self.wis)

    @wis_mod.setter
    def wis_mod(self, x):
        pass

    @property
    def cha_mod(self):
        return self.ability_modifier(self.cha)

    @cha_mod.setter
    def char_mod(self, x):
        pass

    def ability_modifier(self, stat):
        return floor((stat - 10) / 2)

    armor = attrib(default=attr_factory(list))
    speed = attrib(default=30)
    skills = attrib(default=attr_factory(dict))
    resist = attrib(default=attr_factory(list))
    immune = attrib(default=attr_factory(list))
    languages = attrib(default=attr_factory(list))
    features = attrib(default=attr_factory(dict))
    actions = attrib(default=attr_factory(dict))
    reactions = attrib(default=attr_factory(dict))
    notes = attrib(default="")
    origin = attrib(default="origin unknown")


@attrs
class Encounter:

    name = attrib(default="")
    location = attrib(default="")
    notes = attrib(default="")
    groups = attrib(default=[])



