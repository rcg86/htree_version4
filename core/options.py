"""Cadence-style option parsing for commands: -name value, -flag, positionals."""

from core.messages import HtreeError

USAGE_ERROR = 1


def parse_options(cmd: str, argv, spec: dict, max_positionals: int = 0):
    """Parse argv against spec {'-file': 'value', '-overwrite': 'flag'}.

    Returns (opts, positionals). Flags not given are False; values not given are
    absent from opts.
    """
    opts = {name: False for name, kind in spec.items() if kind == "flag"}
    positionals = []
    i = 0
    while i < len(argv):
        word = argv[i]
        if word.startswith("-") and len(word) > 1 and not _is_number(word):
            if word not in spec:
                raise HtreeError(USAGE_ERROR, f"{cmd}: unknown option '{word}'. "
                                 f"Valid options: {' '.join(sorted(spec)) or 'none'}")
            if spec[word] == "flag":
                opts[word] = True
            else:
                if i + 1 >= len(argv):
                    raise HtreeError(USAGE_ERROR, f"{cmd}: option '{word}' needs a value")
                opts[word] = argv[i + 1]
                i += 1
        else:
            positionals.append(word)
        i += 1
    if len(positionals) > max_positionals:
        raise HtreeError(USAGE_ERROR, f"{cmd}: unexpected argument '{positionals[max_positionals]}'")
    return opts, positionals


def _is_number(word: str) -> bool:
    try:
        float(word)
        return True
    except ValueError:
        return False
