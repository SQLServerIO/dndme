import random


def roll_dice(times, sides, modifier=0, dice_mult=1, total_mult=1):
    """
    Simulate a dice roll of XdY + Z.

    "Rolls" a die of Y sides X times, gets the sum, and adjusts it by an
    optional modifier. Pass either a dice multiplier or total multiplier
    to support critical hit damage for 5E or 2E/3E rules.

    Example usage:

       # Stats: 3d6
       >>> roll_dice(3, 6)
       # Saving throw: 1d20
       >>> roll_dice(1, 20)
       # Damage (longsword +1): 1d8 + 1
       >>> roll_dice(1, 8, modifier=1)
       # Damage (cursed longsword - 2): 1d8 - 2
       >>> roll_dice(1, 8, modifier=-2)
       # Damage (crit, 5E)
       >>> roll_dice(1, 8, dice_mult=2)
       # Damage (crit, 2E)
       >>> roll_dice(1, 8, total_mult=2)
    """
    randint = random.randint
    dice_result = sum(map(lambda x: randint(1, sides), range(times)))
    return total_mult * (dice_mult * dice_result + modifier)
