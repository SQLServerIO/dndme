import sys
from dndme.commands import Command


class Quit(Command):

    keywords = ['quit', 'exit']
    help_text = """{keyword}
{divider}
Summary: Quit the shell

Usage: {keyword}
"""

    def do_command(self, *args):
        print("Goodbye!")
        try:
            sys.exit(0)
        except:
            exit(0)
