"""move_spine_to_boundary -spine <spine> -moves <moves> [-clearance <l r t b>]:
bend a built spine along a path, like the snake of the game.

    move_spine_to_boundary -spine temp -clearance {10 10 10 10} \\
        -moves {head bottom down 679.68 left 103.68 head top down 23.04}

The spine (its mirror included) is one body on the line of its stubs. A move
pulls one end, the head, up, down, left or right, and the body follows along
the path the head has drawn: every cell, stub and net centre line keeps its
distance along the spine and its side of it, so the stub lengths and gaps,
the spacing of the cells and the drive lengths stay; a stub over a corner is
L-shaped. See core/spine_snake.py for the moves and the hard stops.

When all the moves are made the spine is stored on its new path, its routing
is removed (pin routes, net routes, stub wires and shields: route_pin,
route_net and route_final_stub build them again) and its cells are put on
legal sites (legalize_placement). A move that would run the spine into its
own body is an error and nothing changes.
"""

from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.spine_snake import DIRS, SIDES, Snake, SnakeError

NAME = "move_spine_to_boundary"
SUMMARY = "Bend a built spine along a path of head moves (the snake), up to the boundary"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-spine": "value", "-moves": "value", "-clearance": "value"}

USAGE = 1
NO_SPINE = 230
BAD_MOVES = 231
STOPPED = 232
SELF_HIT = 233
OUTSIDE = 234
NO_ROWS = 235
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    usage = ("Usage: move_spine_to_boundary -spine <spine> -moves {head <end> <direction> "
             "<um> ...} [-clearance {<left> <right> <top> <bottom>}]")
    if "-spine" not in opts or "-moves" not in opts:
        raise HtreeError(USAGE, f"move_spine_to_boundary: -spine and -moves are required. "
                         f"{usage}")
    db = session.db
    name = opts["-spine"].removeprefix("spine:")
    if db.spine_row(name) is None:
        raise HtreeError(NO_SPINE, f"move_spine_to_boundary: no built spine '{name}' "
                         f"(create_spine -build; get_db spines lists them)")
    clearance = _clearance(session, opts.get("-clearance"))
    try:
        snake = Snake(db, name, clearance)
    except SnakeError as exc:
        raise HtreeError(NO_SPINE, f"move_spine_to_boundary: {exc}")
    out = session.out
    for word, value in _moves(session, snake, opts["-moves"]):
        if word == "head":
            snake.set_head(value)
            continue
        step = snake.move(word, value)
        if step.note.startswith("refused"):
            raise HtreeError(SELF_HIT, f"move_spine_to_boundary: {word} {_num(value)} (head "
                             f"{snake.end_name()}) {step.note}; nothing changed")
        where = f"head {snake.end_name()} at {_num(step.head[0])} {_num(step.head[1])}"
        if step.note:
            warn(STOPPED, f"{word} {_num(value)}: moved {_num(step.moved)}, {step.note}; "
                 f"{where}", out)
        elif abs(step.moved - value) > TOL:
            info(f"  {word} {_num(value)}: moved {_num(step.moved)} to the signal track; "
                 f"{where}", out)
        else:
            info(f"  {word} {_num(value)}: {where}", out)
    return finish(session, snake)


def finish(session, snake):
    """Store the spine as snake has it, drop its routing, report what is
    outside the boundary and legalize its cells. Returns its handle."""
    db, out, name = session.db, session.out, snake.name
    lapped = snake.cell_overlaps()
    straps, pin_wires, net_wires = snake.commit(db)
    corners = len(snake.body()) - 2
    info(f"Moved spine:{name} onto a path with {corners} corner(s): "
         f"{len(snake.members)} instances, {len(snake.stubs)} stubs, {len(snake.nets)} nets. "
         f"Removed its routing: {straps} strap(s), {pin_wires} pin wire(s), {net_wires} net "
         f"wire(s); run route_pin, route_net and route_final_stub again", out)
    outside = snake.outside()
    if outside:
        warn(OUTSIDE, f"spine {name}: {len(outside)} cell(s) or stub(s) outside the design "
             f"boundary: {' '.join(outside)}", out)
    if lapped:
        info(f"  {len(lapped)} pair(s) of its cells overlap where the path bends; "
             f"legalizing", out)
    insts = [m[0] for m in snake.members]
    if db.has_site_rows():
        from core.commands import legalize_placement
        legalize_placement.run(session, ["-inst", " ".join(insts)])
    else:
        warn(NO_ROWS, f"spine {name}: no placement rows (read_def a DEF with ROW "
             f"statements), so its cells are on the manufacturing grid, not on sites"
             + (f", and {len(lapped)} pair(s) overlap" if lapped else ""), out)
    return f"spine:{name}"


def _clearance(session, text):
    """(left, right, top, bottom) um from -clearance; zeros without it."""
    if text is None:
        return (0.0,) * 4
    words = session.split_list(text)
    try:
        values = tuple(float(w) for w in words)
    except ValueError:
        values = ()
    if len(values) != 4 or min(values) < 0:
        raise HtreeError(USAGE, f"move_spine_to_boundary: -clearance takes four distances, "
                         f"um, 0 or more: {{{' '.join(SIDES)}}}; got '{text}'")
    return values


def _moves(session, snake, text):
    """[('head', end) | (direction, um)] from -moves, checked."""
    words = session.split_list(text)
    form = (f"-moves is a list of 'head <{'|'.join(snake.ends)}>' and '<up|down|left|right> "
            f"<um>' pairs")
    if not words or len(words) % 2:
        raise HtreeError(BAD_MOVES, f"move_spine_to_boundary: {form}; got '{text}'")
    found = []
    for word, value in zip(words[0::2], words[1::2]):
        if word == "head":
            if value not in snake.ends:
                raise HtreeError(BAD_MOVES, f"move_spine_to_boundary: the ends of spine "
                                 f"{snake.name} are {' and '.join(snake.ends)}, not "
                                 f"'{value}'")
            found.append((word, value))
            continue
        try:
            distance = float(value)
        except ValueError:
            distance = -1.0
        if word not in DIRS or distance <= 0:
            raise HtreeError(BAD_MOVES, f"move_spine_to_boundary: {form}; got '{word} "
                             f"{value}'")
        found.append((word, distance))
    if not any(w != "head" for w, _ in found):
        raise HtreeError(BAD_MOVES, f"move_spine_to_boundary: -moves has no move; {form}")
    return found
