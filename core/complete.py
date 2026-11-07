"""Tab completion for the interactive shell (GNU readline).

    <tab> on a command name           command names
    get_db .<tab>                     path roots (tech, library_physical)
    get_db .tech.<tab>                what tech holds: layer, layers, file, ...
    get_db .tech.layer.<tab>          attributes of layer objects
    get_db layer:<tab>                layer handles (lib_cell:, lib_pin: likewise)
    get_db <objects> .<tab>           attributes of those objects
    get_db <objects> -if {.<tab>      attributes of those objects
    any other word                    file names

The list shown on a double <tab> holds only the last path segment ('layer',
not '.tech.layer'), like a directory listing. The leading dot on paths is
optional.
"""

import glob
import os
import shutil

from core import objects

# Path root -> object type it yields. Aliases complete only once typed.
ROOT_TYPES = {"tech": "tech", "head": "tech", "layers": "layer", "layer": "layer",
              "library_physical": "library_physical", "lib_cells": "lib_cell",
              "lib_cell": "lib_cell", "spine_specs": "spine_spec",
              "spine_spec": "spine_spec", "design": "design", "designs": "design",
              "ports": "port", "port": "port", "track_patterns": "track_pattern",
              "track_pattern": "track_pattern", "selected": None,   # None: mixed types
              "track_assignments": "track_assignment", "track_assignment": "track_assignment"}
SHOWN_ROOTS = ["tech", "library_physical", "spine_spec", "design"]
DELIMS = " \t\n[]{}()\"';"
GET_DB_OPTIONS = ["-if"]


class Completer:
    def __init__(self, session):
        self.session = session
        self.matches = []
        self.leaf_display = False

    def candidates(self, line: str, begidx: int, text: str):
        """All completions for 'text', which starts at line[begidx]."""
        self.leaf_display = False
        words = _command_words(line[:begidx])
        if not words:
            return [c + " " for c in sorted(self.session.commands) if c.startswith(text)]
        if words[0] == "get_db":
            matches = self._get_db(words[1:], text)
            self.leaf_display = any(m.startswith(".") or "." in m for m in matches)
            return matches
        return _files(text)

    # readline interface -----------------------------------------------------

    def complete(self, text, state):
        import readline
        if state == 0:
            try:
                self.matches = self.candidates(readline.get_line_buffer(),
                                               readline.get_begidx(), text)
            except Exception:       # never let a completion bug kill the prompt
                self.matches = []
        return self.matches[state] if state < len(self.matches) else None

    def display(self, substitution, matches, longest, prompt):
        import readline
        names = [_leaf(m) if self.leaf_display else m.rstrip() for m in matches]
        width = max(len(n) for n in names) + 2
        cols = max(1, shutil.get_terminal_size().columns // width)
        rows = [names[i:i + cols] for i in range(0, len(names), cols)]
        out = self.session.out
        print(file=out)
        for row in rows:
            print("".join(n.ljust(width) for n in row).rstrip(), file=out)
        out.flush()
        if _FORCED_REDISPLAY is not None:
            _FORCED_REDISPLAY()      # readline redraws prompt and line, cursor in place
        else:
            print(prompt + readline.get_line_buffer(), end="", file=out, flush=True)

    # get_db -----------------------------------------------------------------

    def _get_db(self, args, text):
        if text.startswith("-"):
            return [o + " " for o in GET_DB_OPTIONS if o.startswith(text)]
        if "-if" in args:
            if not text.startswith("."):
                return []
            return _attrs(_target_types(args[0]) if args else list(objects.ATTRS),
                          text[1:].split("."), ".")
        if not args:
            return self._path(text)
        if len(args) == 1 and text.startswith("."):
            segs = text[1:].split(".")
            extra = [".* "] if segs == [""] else []
            return extra + _attrs(_target_types(args[0]), segs, ".")
        return []

    def _path(self, text):
        dot = "." if text.startswith(".") else ""
        body = text[len(dot):]
        if not dot and ":" in body and "." not in body:
            return self._handles(body)
        segs = body.split(".")
        if len(segs) == 1:
            roots = SHOWN_ROOTS if not body else [r for r in ROOT_TYPES if r.startswith(body)]
            return [dot + r for r in roots]
        if segs[0] not in ROOT_TYPES:
            return []
        kind = ROOT_TYPES[segs[0]]
        return _attrs([kind] if kind else list(objects.ATTRS), segs[1:], dot + segs[0] + ".")

    def _handles(self, word):
        kind, _, pattern = word.partition(":")
        db = self.session.db
        if kind == "layer" and db.has_tech():
            names = db.layer_names()
        elif kind == "lib_cell" and db.has_library():
            names = db.lib_cell_names()
        elif kind == "lib_pin" and db.has_library():
            names = [f"{c}/{p}" for c, p in db.all_lib_pins()]
        elif kind == "spine_spec" and db.has_spine_specs():
            names = db.spine_spec_names()
        elif kind == "track_assignment":
            names = db.track_assignment_layers()
        elif kind == "design" and db.has_design():
            names = [db.design_row()["name"]]
        elif kind == "port" and db.has_design():
            top = db.design_row()["name"]
            names = [f"{top}/{p}" for p in db.port_names()]
        else:
            return []
        return [f"{kind}:{n} " for n in names if n.startswith(pattern)]


def _attrs(kinds, segs, prefix):
    """Complete the last of 'segs', after walking the relations named by the rest."""
    out = []
    for kind in kinds:
        for seg in segs[:-1]:
            kind = objects.RELATIONS.get((kind, seg))
            if kind is None:
                break
        if kind is None:
            continue
        head = prefix + "".join(s + "." for s in segs[:-1])
        for attr in objects.ATTRS[kind]:
            # A relation can be followed by '.', so it gets no trailing space.
            match = head + attr + ("" if (kind, attr) in objects.RELATIONS else " ")
            if attr.startswith(segs[-1]) and match not in out:
                out.append(match)
    return out


def _target_types(word):
    """Object types a get_db first word yields; all types when it cannot be told."""
    word = word[1:] if word.startswith(".") else word
    if objects.is_handle(word) and objects.obj_type(word) in objects.ATTRS:
        return [objects.obj_type(word)]
    segs = word.split(".")
    kind = ROOT_TYPES.get(segs[0])
    for seg in segs[1:]:
        if kind is None:
            break
        kind = objects.RELATIONS.get((kind, seg))
    return [kind] if kind else list(objects.ATTRS)


def _command_words(prefix):
    """Words of the command being typed at the end of 'prefix'.

    Starts after the last unclosed '[' or a top-level ';'. Braced and
    bracketed groups count as one word.
    """
    opens = []
    for i, ch in enumerate(prefix):
        if ch == "[":
            opens.append(i)
        elif ch == "]" and opens:
            opens.pop()
    start = opens[-1] + 1 if opens else 0
    words, word, depth = [], "", 0
    for ch in prefix[start:]:
        if depth == 0 and ch in ";\n":
            words, word = [], ""
            continue
        if depth == 0 and ch.isspace():
            if word:
                words.append(word)
            word = ""
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}" and depth:
            depth -= 1
        word += ch
    if word:
        words.append(word)
    return words


def _leaf(match):
    match = match.rstrip()
    return match.rsplit(".", 1)[-1] if match not in (".*",) else match


def _files(text):
    out = []
    for path in sorted(glob.glob(os.path.expanduser(text) + "*")):
        out.append(path + ("/" if os.path.isdir(path) else " "))
    return out


_FORCED_REDISPLAY = None


def _load_forced_redisplay(readline):
    """rl_forced_update_display() from the GNU readline the module links to.

    Python does not expose it. Without it, a redraw done here leaves readline's
    idea of the screen stale and inserted text shows up twice.
    """
    try:
        import ctypes
        return ctypes.CDLL(readline.__file__).rl_forced_update_display
    except (OSError, AttributeError):
        return None


def install(session, prompt_fn):
    """Hook the completer into readline. prompt_fn returns the current prompt."""
    global _FORCED_REDISPLAY
    import readline
    _FORCED_REDISPLAY = _load_forced_redisplay(readline)
    completer = Completer(session)
    readline.set_completer(completer.complete)
    readline.set_completer_delims(DELIMS)
    readline.set_completion_display_matches_hook(
        lambda sub, matches, longest: completer.display(sub, matches, longest, prompt_fn()))
    readline.parse_and_bind("tab: complete")
    # List choices on the first <tab>, as Innovus does, instead of a bell.
    readline.parse_and_bind("set show-all-if-ambiguous on")
    return completer
