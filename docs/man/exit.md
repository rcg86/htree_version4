NAME
    exit - exit the tool

SYNOPSIS
    exit [<code>]

DESCRIPTION
    Leaves the tool immediately, including from inside a script run with
    -init or source. The in-memory database is not saved; run write_db
    first if you need it.

OPTIONS
    <code>
        Process exit status. Default 0.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    Does not return.

EXAMPLES
    htree> write_db -file design.db
    htree> exit

ERRORS
    HT4-001  exit code is not an integer

SEE ALSO
    write_db
