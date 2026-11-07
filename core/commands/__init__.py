"""Command registry. Every module in this package is one command and defines:

    NAME     the Tcl command name
    SUMMARY  one line for 'help'
    run(session, argv) -> str | tuple | list | None
"""

import importlib
import pkgutil


def discover() -> dict:
    commands = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        for attr in ("NAME", "SUMMARY", "run"):
            if not hasattr(module, attr):
                raise ImportError(f"command module {info.name} has no {attr}")
        commands[module.NAME] = module
    return commands
