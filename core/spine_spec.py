"""Spine spec YAML parser. Pure: reads a file, returns dataclasses, never touches the db.

A file holds one or more specs, either as YAML documents separated by '---'
(each with a 'spine_spec:' mapping) or as a list under 'spine_spec:'.
Duplicate keys are an error: plain YAML loaders keep the last one silently,
which merges two specs into one.

Nothing is dropped. Keys that are not modeled go to SpineSpec.extra (or the
cell's extra) verbatim as 'path: value', and each spec keeps its source text.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

import yaml


class SpineSpecError(Exception):
    def __init__(self, text: str, file: str, line: Optional[int] = None):
        where = f"{file}, line {line}" if line else file
        super().__init__(f"{where}: {text}")
        self.text = text
        self.file = file
        self.line = line


@dataclass
class SpineCell:
    name: str
    input: Optional[str] = None
    output: Optional[str] = None
    location: Optional[float] = None   # along the spine from its driver, um
    extra: List[str] = field(default_factory=list)


@dataclass
class SpineLevel:
    name: str
    cells: List[SpineCell] = field(default_factory=list)


@dataclass
class SpineSpec:
    name: str
    line: int
    type: Optional[str] = None
    units: Optional[str] = None
    point: Optional[str] = None
    root_net: Optional[str] = None
    max_drive_length: Optional[float] = None
    count_stub_in_drive: Optional[bool] = None
    origin_x: Optional[float] = None
    origin: Optional[float] = None     # along the spine, -location to L1
    level_pitch: Optional[float] = None
    deviation: Optional[float] = None
    orientation: Optional[str] = None
    span: Optional[float] = None
    stub_count: Optional[int] = None
    stub_gap: Optional[float] = None
    stub_tap: Optional[str] = None
    stub_order: Optional[List[str]] = None
    levels: List[SpineLevel] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)
    yaml_text: str = ""


@dataclass
class SpineSpecFile:
    file: str
    specs: List[SpineSpec] = field(default_factory=list)
    ignored: List[tuple] = field(default_factory=list)    # (top-level key, line)


# Modeled keys: (section or None for top level, key) -> (SpineSpec attr, kind).
FIELDS = {
    (None, "type"): ("type", "str"),
    (None, "units"): ("units", "str"),
    (None, "point"): ("point", "str"),
    (None, "root_net"): ("root_net", "str"),
    ("constraints", "max_drive_length"): ("max_drive_length", "num"),
    ("constraints", "count_stub_in_drive"): ("count_stub_in_drive", "bool"),
    ("placement", "origin_x"): ("origin_x", "num"),
    ("placement", "origin"): ("origin", "num"),
    ("placement", "level_pitch"): ("level_pitch", "num"),
    ("placement", "deviation"): ("deviation", "num"),
    ("spine", "orientation"): ("orientation", "str"),
    ("spine", "span"): ("span", "num"),
    ("stubs", "count"): ("stub_count", "int"),
    ("stubs", "gap"): ("stub_gap", "num"),
    ("stubs", "tap"): ("stub_tap", "str"),
    ("stubs", "order"): ("stub_order", "list"),
}
# Older keys still read, as the key they became. orientation decides the
# axis of level_pitch, so one key serves vertical and horizontal spines.
ALIASES = {("placement", "level_pitch_x"): "level_pitch",
           ("placement", "level_pitch_y"): "level_pitch"}
SECTIONS = {s for s, _ in FIELDS if s}
KIND_TEXT = {"str": "a string", "num": "a number", "int": "an integer",
             "bool": "true or false", "list": "a list of names"}


class _Map(dict):
    """A YAML mapping that remembers where it starts and ends (1-based lines)."""
    line = 0
    end_line = 0


class _Loader(yaml.SafeLoader):
    pass


def _construct_map(loader, node):
    data = _Map()
    data.line = node.start_mark.line + 1
    data.end_line = node.end_mark.line + 1
    yield data
    seen = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        line = key_node.start_mark.line + 1
        if key in seen:
            raise _Duplicate(key, line, seen[key])
        seen[key] = line
    data.update(loader.construct_mapping(node, deep=True))


class _Duplicate(Exception):
    def __init__(self, key, line, first):
        super().__init__(key)
        self.key, self.line, self.first = key, line, first


_Loader.add_constructor("tag:yaml.org,2002:map", _construct_map)


def parse_spine_spec(path: str) -> SpineSpecFile:
    with open(path) as fh:
        text = fh.read()
    return _Parser(path, text).parse()


class _Parser:
    def __init__(self, path: str, text: str):
        self.path = path
        self.lines = text.splitlines()
        self.text = text

    def error(self, text: str, line: Optional[int] = None):
        raise SpineSpecError(text, self.path, line)

    def parse(self) -> SpineSpecFile:
        try:
            docs = list(yaml.load_all(self.text, Loader=_Loader))
        except _Duplicate as dup:
            self.error(f"duplicate key '{dup.key}' (first at line {dup.first}). To put "
                       f"several specs in one file, start each with '---' and "
                       f"'spine_spec:', or list them under 'spine_spec:'", dup.line)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            problem = getattr(exc, "problem", None) or str(exc)
            if "mapping values are not allowed" in problem:
                problem += " (check the indentation: this line is indented differently " \
                           "from the keys above it)"
            self.error(f"YAML syntax: {problem}", mark.line + 1 if mark else None)

        result = SpineSpecFile(file=self.path)
        for doc in docs:
            if doc is None:
                continue
            if not isinstance(doc, dict):
                self.error("expected 'spine_spec:' at the top of the document")
            for key, value in doc.items():
                if key != "spine_spec":
                    result.ignored.append((key, getattr(doc, "line", None)))
                    continue
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if not isinstance(item, dict):
                        self.error("each spine_spec must be a mapping of keys",
                                   getattr(doc, "line", None))
                    result.specs.append(self.spec(item))
        names = {}
        for spec in result.specs:
            if spec.name in names:
                self.error(f"spine_spec '{spec.name}' is defined twice "
                           f"(first at line {names[spec.name]})", spec.line)
            names[spec.name] = spec.line
        if not result.specs:
            self.error("no spine_spec found")
        return result

    def spec(self, data: _Map) -> SpineSpec:
        name = data.get("name")
        if not isinstance(name, str) or not name:
            self.error("spine_spec has no 'name' (a non-empty string)", data.line)
        self.check_name(name, "spine_spec name", data.line)
        spec = SpineSpec(name=name, line=data.line, yaml_text=self.source(data))
        for key, value in data.items():
            if key == "name":
                continue
            if key == "levels":
                spec.levels = self.levels(spec, value, data.line)
            elif key in SECTIONS:
                if not isinstance(value, dict):
                    self.error(f"{name}: '{key}' must be a mapping of keys", data.line)
                for sub, subval in value.items():
                    self.field(spec, key, sub, subval, getattr(value, "line", data.line))
            else:
                self.field(spec, None, key, value, data.line)
        return spec

    def field(self, spec, section, key, value, line):
        path = f"{section}.{key}" if section else key
        key = ALIASES.get((section, key), key)
        if (section, key) == ("placement", "level_pitch") and spec.level_pitch is not None:
            self.error(f"{spec.name}: give only one of placement.level_pitch, "
                       f"level_pitch_x and level_pitch_y", line)
        target = FIELDS.get((section, key))
        if target is None:
            spec.extra.append(f"{path}: {_flow(value)}")
            return
        attr, kind = target
        if value is not None and not _is_kind(value, kind):
            self.error(f"{spec.name}: '{path}' must be {KIND_TEXT[kind]}, got {_flow(value)}",
                       line)
        setattr(spec, attr, value)

    def levels(self, spec, value, line):
        if not isinstance(value, dict):
            self.error(f"{spec.name}: 'levels' must be a mapping of level names", line)
        levels = []
        for lname, ldata in value.items():
            lname = str(lname)
            lline = getattr(value, "line", line)
            self.check_name(lname, f"{spec.name}: level name", lline)
            level = SpineLevel(name=lname)
            if ldata is None:
                ldata = {}
            if not isinstance(ldata, dict):
                self.error(f"{spec.name}: level '{lname}' must be a mapping with 'cells'", lline)
            for key, kval in ldata.items():
                if key != "cells":
                    spec.extra.append(f"levels.{lname}.{key}: {_flow(kval)}")
                    continue
                level.cells = self.cells(spec, lname, kval, getattr(ldata, "line", lline))
            levels.append(level)
        return levels

    def cells(self, spec, lname, value, line):
        if value is None:
            return []
        if not isinstance(value, dict):
            self.error(f"{spec.name}: {lname}.cells must be a mapping of cell names", line)
        cells = []
        for cname, cdata in value.items():
            cname = str(cname)
            cline = getattr(value, "line", line)
            self.check_name(cname, f"{spec.name}: {lname} cell name", cline)
            cell = SpineCell(name=cname)
            if cdata is None:
                cdata = {}
            if not isinstance(cdata, dict):
                self.error(f"{spec.name}: {lname}/{cname} must be a mapping "
                           f"like {{input: ..., output: ...}}", cline)
            for key, kval in cdata.items():
                if key in ("input", "output"):
                    if kval is not None and not isinstance(kval, str):
                        self.error(f"{spec.name}: {lname}/{cname} {key} must be a string, "
                                   f"got {_flow(kval)}", cline)
                    setattr(cell, key, kval)
                elif key == "location":
                    if kval is not None and not _is_kind(kval, "num"):
                        self.error(f"{spec.name}: {lname}/{cname} location must be a number "
                                   f"(um from its driver along the spine), got {_flow(kval)}",
                                   cline)
                    cell.location = kval
                else:
                    cell.extra.append(f"{key}: {_flow(kval)}")
            cells.append(cell)
        return cells

    def check_name(self, name, what, line):
        if "/" in name or any(c.isspace() for c in name):
            self.error(f"{what} '{name}' must not contain '/' or spaces", line)

    def source(self, data: _Map) -> str:
        """The spec's own lines from the file, without trailing blank or '---' lines."""
        start = data.line - 1
        # A block mapping starts at its first key; include the 'spine_spec:' or
        # '- ' line above it when that is where the spec begins.
        if start > 0 and self.lines[start - 1].strip() in ("spine_spec:", "-"):
            start -= 1
        lines = self.lines[start:data.end_line]
        while lines and lines[-1].strip() in ("", "---", "..."):
            lines.pop()
        return "\n".join(lines)


def _is_kind(value: Any, kind: str) -> bool:
    if kind == "str":
        return isinstance(value, str)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, list) and all(isinstance(v, str) for v in value)   # list


def _flow(value) -> str:
    """One-line YAML text for a value: 3, true, [a, b], {input: net}."""
    return yaml.safe_dump(value, default_flow_style=True, width=10**6).strip() \
        .removesuffix("\n...").removesuffix("...").strip()
