NAME
    write_db - write the design database to a SQLite file

SYNOPSIS
    write_db -file <file> [-overwrite]

DESCRIPTION
    The design database lives in memory while the tool runs. write_db saves
    a complete copy to <file> as a SQLite database. read_db -file <file>
    loads it back in a later session, which then continues from this
    point. The file can also be opened with any SQLite client.

    An existing file is replaced only with -overwrite. The copy is written
    to a temporary file beside <file> and then renamed, so a failed write
    leaves any existing file untouched.

    The file may also be given without -file (write_db <file>).

OPTIONS
    -file <file>
        Output file. Required.
    -overwrite
        Replace <file> if it exists.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None. Prints the absolute path written.

EXAMPLES
    htree> write_db -file design.db
    Database written to '/path/to/design.db'
    htree> write_db -file design.db -overwrite

ERRORS
    HT4-001  file name missing or given twice, or an unknown option
    HT4-030  file exists and -overwrite was not given
    HT4-031  write failed

SEE ALSO
    read_db, read_tech, get_db
