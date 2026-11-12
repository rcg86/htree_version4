"""set_db <objects> <.attr> <value>: set an attribute on objects in the database.
set_db <root_attr> <value>: set a root attribute (a setting of the commands).

    set_db [get_db nets *L4*] .route_rule rule1
    set_db spine_net:sp1/sp1_L1_1_Y .route_rule default
    set_db [get_db insts] .place_status fixed
    set_db ignore_shield_less_than_routing_length 20

Only the attributes in SETTABLE can be set; every object is checked before
any is changed.
"""

from core import objects, root_attrs
from core.commands.create_route_rule import DEFAULT
from core.commands.select_obj import handles_from
from core.db import _num
from core.messages import HtreeError, info, warn

NAME = "set_db"
SUMMARY = "Set an attribute on objects (e.g. a net's .route_rule)"

USAGE = 1
NOT_SETTABLE = 140
BAD_VALUE = 141
NO_OBJECTS = 142


def _route_rule_value(db, value):
    """Rule name for .route_rule; None is the default rule."""
    name = value.removeprefix("route_rule:")
    if name == DEFAULT:
        return None
    if not db.route_rule_layers(name):
        raise HtreeError(BAD_VALUE, f"set_db: there is no route rule '{name}' (rules: "
                         f"{' '.join([DEFAULT] + db.route_rule_names())}); create it with "
                         f"create_route_rule")
    return name


def _set_net_route_rule(db, handle, rule):
    if objects.obj_type(handle) == "stub":     # stubs are nets too, keyed apart
        spine, _, stub = handle.partition(":")[2].partition("/")
        db.set_net_route_rule(objects.stub_key(spine, stub), rule)
    else:
        db.set_net_route_rule(objects.name_of(handle), rule)


PLACE_STATUSES = ("placed", "fixed", "cover")


def _place_status_value(db, value):
    status = value.lower()
    if status not in PLACE_STATUSES:
        raise HtreeError(BAD_VALUE, f"set_db: .place_status must be one of "
                         f"{' '.join(PLACE_STATUSES)}, got '{value}'")
    return status


def _set_inst_status(db, handle, status):
    db.set_inst_status(objects.name_of(handle), status)


# (object type, attr) -> (value check returning the stored value, setter)
SETTABLE = {("spine_net", "route_rule"): (_route_rule_value, _set_net_route_rule),
            ("stub", "route_rule"): (_route_rule_value, _set_net_route_rule),
            ("inst", "place_status"): (_place_status_value, _set_inst_status),
            ("inst", "status"): (_place_status_value, _set_inst_status)}


def run(session, argv):
    if len(argv) == 2:                        # set_db <root_attr> <value>
        name = argv[0].removeprefix(".")
        if argv[1].startswith(".") or name not in root_attrs.ATTRS:
            raise HtreeError(USAGE, f"set_db: no value, or no root attribute '{argv[0]}' "
                             f"(root attributes: {' '.join(root_attrs.names())}). Usage: "
                             f"set_db <root_attr> <value> | set_db <objects> <.attr> <value>")
        value = root_attrs.set_value(session.db, name, argv[1])
        info(f"set_db: {name} = {_num(value) if isinstance(value, float) else value}"
             + ("" if root_attrs.is_set(session.db, name) else " (default)"), session.out)
        return _num(value) if isinstance(value, float) else value
    if len(argv) != 3:
        raise HtreeError(USAGE, "set_db: expected 2 or 3 arguments. Usage: set_db <objects> "
                         "<.attr> <value> | set_db <root_attr> <value>")
    target, attr, value = argv
    attr = attr.removeprefix(".")
    db = session.db
    handles = handles_from(session, [target], NAME)
    if not handles:
        warn(NO_OBJECTS, "set_db: no objects given; nothing set", session.out)
        return ""
    for handle in handles:
        kind = objects.obj_type(handle)
        if (kind, attr) not in SETTABLE:
            settable = " ".join(f"{k}.{a}" for k, a in SETTABLE)
            raise HtreeError(NOT_SETTABLE, f"set_db: '{attr}' cannot be set on {kind} "
                             f"objects ({handle}). Settable: {settable}")
    checked = {}
    for handle in handles:
        key = (objects.obj_type(handle), attr)
        check, _ = SETTABLE[key]
        if key not in checked:
            checked[key] = check(db, value)
    for handle in handles:
        key = (objects.obj_type(handle), attr)
        SETTABLE[key][1](db, handle, checked[key])
    return tuple(handles)
