"""Innovus-style messages: **ERROR: (HT4-nnn): text and **WARN: (HT4-nnn): text."""

import sys


class HtreeError(Exception):
    """Raised by a command; the shell prints it and turns it into a Tcl error."""

    def __init__(self, msg_id: int, text: str):
        super().__init__(text)
        self.msg_id = msg_id
        self.text = text

    def formatted(self) -> str:
        return f"**ERROR: (HT4-{self.msg_id:03d}): {self.text}"


def warn(msg_id: int, text: str, out=None):
    print(f"**WARN: (HT4-{msg_id:03d}): {text}", file=out or sys.stdout)


def info(text: str, out=None):
    print(text, file=out or sys.stdout)
