"""help: list all commands with a one-line summary."""

from core.messages import info
from core.options import parse_options

NAME = "help"
SUMMARY = "List all commands"


def run(session, argv):
    parse_options(NAME, argv, {})
    width = max(len(name) for name in session.commands)
    for name in sorted(session.commands):
        info(f"  {name:<{width}}  {session.commands[name].SUMMARY}", session.out)
    info("Run '<command> -help' for usage and an example, 'man <command>' for details.",
         session.out)
    return None
