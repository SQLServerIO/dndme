import re
from dndme.commands import Command


class ShowCalendar(Command):

    keywords = ['calendar', 'cal']
    help_txt = """{keyword}
{divider}
Summary: Show an overview of the calendar for the current year,
or a given year.

Usage:

    {keyword} [year]

Examples:

    {keyword}
    {keyword} 1488
"""

    def do_command(self, *args):
        calendar = self.game.calendar
        
        if args:
            try:
                year = int(args[0])
            except ValueError:
                print(f"Invalid year: {year}")
                return
        else:
            year = calendar.year

        self.print(f"<x1>{year}</x1>")
        print("-" * 20)
        for key, month in calendar.cal_data['months'].items():
            days_in_month = calendar.days_in_month(key, year)
            if days_in_month == 0:
                continue
            elif days_in_month == 1:
                self.print(f"     <x>{month['name']}</x>")
            else:
                print(f"1-{days_in_month} {month['name']}")