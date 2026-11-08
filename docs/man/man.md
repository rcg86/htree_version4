NAME
    man - show the manual page for a command

SYNOPSIS
    man <command>

DESCRIPTION
    Prints the manual page for <command>. Pages are the files
    docs/man/<command>.md in the tool directory.

    '<command> -help' prints the short form of the same page: NAME,
    SYNOPSIS, the first paragraph of DESCRIPTION, OPTIONS and the first
    example that runs the command.

OPTIONS
    <command>
        Command name. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None.

EXAMPLES
    htree> man get_db

ERRORS
    HT4-001  command name missing
    HT4-050  no manual page for that command

SEE ALSO
    help
