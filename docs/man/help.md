NAME
    help - list all commands

SYNOPSIS
    help

DESCRIPTION
    Lists every htree command with a one-line summary. Standard Tcl
    commands (set, foreach, puts, source, exit, ...) are also available
    and are not listed.

    Every command also takes -help, which prints its definition, usage,
    options and an example; 'man <command>' prints the full page.

OPTIONS
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None.

EXAMPLES
    htree> help

SEE ALSO
    man
