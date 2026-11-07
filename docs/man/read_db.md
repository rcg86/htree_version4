NAME
    read_db - read a design database written by write_db

SYNOPSIS
    read_db <file>

DESCRIPTION
    Loads a SQLite database written by write_db into memory, replacing the
    current database. The file is opened read-only and is not changed.
    The file's schema version must match this tool's schema version.

OPTIONS
    <file>
        Database file. Required.

RETURN VALUE
    None. Prints the absolute path read.

EXAMPLES
    htree> read_db design.db
    Database read from '/path/to/design.db'
    htree> get_db tech.layer

ERRORS
    HT4-001  file name missing, or an unknown option
    HT4-040  file not found
    HT4-041  not an htree database, or schema version mismatch

SEE ALSO
    write_db, get_db
