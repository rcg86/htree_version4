NAME
    source - run the commands in a script file

SYNOPSIS
    source [-echo] [-encoding <encoding>] <file>

DESCRIPTION
    Reads <file> and runs its commands one after another, as if they were
    typed at the htree> prompt. Any htree command (read_tech, read_lef,
    get_db, write_db, ...) and any Tcl command (set, foreach, proc, puts,
    if, ...) can be used. Commands may span several lines inside braces,
    brackets or quotes, or with a trailing backslash. Variables and procs
    the file defines stay defined afterwards. Scripts may source other
    scripts.

    The first command that fails stops the file. The error message of the
    failing command is printed, followed by the file and line where the
    script stopped (HT4-071). When one script sources another, each level
    reports its own file and line, outermost last. Wrap a command in
    'catch' to keep going past an error.

    'return' at the top level of the file ends the file early. 'exit'
    leaves the tool, also from inside a sourced file.

    'htree_builder -init <file>' runs the file the same way.

OPTIONS
    -echo
        Print each command, prefixed with "htree> ", before running it.
        Comment-only lines are not printed.
    -encoding <encoding>
        Text encoding of the file. Default utf-8. Accepted so that Tcl
        packages calling 'source -encoding utf-8 <file>' work.

    <file>
        Script to run. Relative paths are relative to the current
        directory. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The result of the last command in the file, or the value given to
    'return'.

EXAMPLES
    htree> source run.tcl
    htree> source -echo run.tcl
    htree> read_tech -file tech.lef
    ...
    A script that stops on an error:
    **ERROR: (HT4-022): object 'layer:XX' does not exist
    **ERROR: (HT4-071): source: stopped at run.tcl line 3

ERRORS
    HT4-001  missing file name, or an unknown option
    HT4-070  file not found or not readable
    HT4-071  a command in the file failed (message gives file and line),
             or the file ends inside an unclosed brace, bracket or quote

SEE ALSO
    help, exit
