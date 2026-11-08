# htree4 CUI, slice 1: tech database, `read_tech`, `get_db`, `write_db`, `read_db`

Date: 2026-11-06
Status: implemented (slice 1), 2026-11-06

## 1. Intent

htree_version4 is a new tool for building clock H-trees, including clock
spine structures that v3 (`../htree_version3/htree_tool`) cannot express. v3
kept its design data as hand-written YAML. v4 keeps all design data in a
SQLite database and exposes it through a command-line user interface (CUI)
modeled on Cadence Innovus Stylus Common UI. A GUI comes later and will sit on
the same database.

This document covers only the first slice: the CUI shell itself, the database
plumbing, reading the tech LEF, and querying it with `get_db`. Later slices add
the boundary, ports, instances, nets, routes, vias, tracks, blockages and
routing blockages, each as new commands and new tables.

The user's direction: **follow Cadence behavior exactly** where Cadence has a
defined behavior. Where this document departs from Cadence it says so.

## 2. Goals (this slice)

1. An interactive CUI shell, `htree4`, that accepts Tcl, the way Innovus does.
2. `read_tech -file <lef>` parses a tech LEF and stores everything in it in the
   database.
3. `get_db` is the only command that reads the database. It supports the three
   forms the user specified (section 6).
4. `write_db <file>` saves the in-memory database to a SQLite file.
   `read_db <file>` loads one back.
5. A manual page for every command, written alongside the command.

## 3. Non-goals (this slice)

- GUI.
- Boundary, ports, instances, nets, routes, vias, tracks, blockages and routing
  blockages. The schema is designed so these become new tables later; no
  tables for them are created now.
- Track derivation from the tech data (later slice; user said tracks come from
  the tech file's pitch/offset, min width and min spacing).
- DEF reading or writing.
- `set_db` or any other command that modifies attributes.

## 4. Anti-goals

- `get_db` behaving differently from Innovus in a way a Cadence user would trip
  over (handle format, `.attr` syntax, `-if` syntax, list return values).
- Silently dropping LEF content. If the parser sees a statement it does not
  model, it keeps it (section 5.3), it does not discard it.
- A command shipped without its manual page.

## 5. Data

### 5.1 Input: `tech.lef`

The current input is `htree_version4/tech.lef` (115 lines, LEF 5.8, updated by
the user on 2026-11-06 to add IB). It contains:

- `VERSION 5.8`
- `UNITS / DATABASE MICRONS 4000`
- `MANUFACTURINGGRID 0.00025`
- Six `LAYER` blocks, all `TYPE ROUTING`: H1, H2, G1, G2, IA, IB. Statements seen:
  `TYPE`, `DIRECTION`, `PITCH x y`, `OFFSET x y`, `WIDTH`, `MINWIDTH`,
  `MAXWIDTH`, `AREA`, `MINENCLOSEDAREA`, `MINSTEP <v> MAXEDGES <n>`.
- `#` comments (rule names such as `# Hx.W.1`).

Known gaps in this file, recorded, not fixed by the tool:

- No `SPACING` statements on any layer. The user expects min spacing to come
  from the tech file; until a file with spacing arrives, `.min_spacing` is
  empty.
- IA and IB have no `MINSTEP`; their `.min_step` is empty. The tool reads what
  the file contains and does not invent values.
- No cut layers, vias, via rules or sites.

`PITCH` and `OFFSET` may also appear with a single value in other LEFs; in that
case x and y take the same value.

### 5.2 Schema

The live database is SQLite in memory (`:memory:`). Tables for this slice:

```
meta   (key TEXT PRIMARY KEY, value TEXT)
       -- schema_version, tool version, source file paths

tech   (id INTEGER PRIMARY KEY CHECK (id = 1),
        lef_version TEXT, db_units INTEGER, manufacturing_grid REAL,
        file TEXT)

layer  (id INTEGER PRIMARY KEY,           -- LEF order, 1-based
        name TEXT UNIQUE NOT NULL,
        type TEXT, direction TEXT,
        pitch_x REAL, pitch_y REAL,
        offset_x REAL, offset_y REAL,
        width REAL, min_width REAL, max_width REAL,
        area REAL, min_enclosed_area REAL,
        min_step REAL, min_step_max_edges INTEGER,
        min_spacing REAL,
        lef_text TEXT)           -- full original LAYER block

layer_extra (layer_id INTEGER REFERENCES layer(id),
             seq INTEGER, statement TEXT)
       -- LEF statements inside a LAYER block the parser does not model,
       -- stored verbatim in file order

tech_extra (seq INTEGER PRIMARY KEY, kind TEXT, line INTEGER, text TEXT)
       -- top-level LEF statements/blocks not modeled, verbatim
```

All distances are stored in microns as REAL, exactly as written in the LEF.
Enumerations (`type`, `direction`) are stored lowercase (`routing`,
`horizontal`), which is how Innovus reports them.

### 5.3 Nothing is dropped (Claude's call)

The parser must work on fuller tech LEFs than the current file, not just this
one.

- Inside a `LAYER` block, any statement not modeled as a column goes into
  `layer_extra` verbatim and appears as `.extra` on the layer.
- `SPACING <value> ;` (plain form, no qualifiers) fills `.min_spacing`; the
  smallest value wins if several plain forms appear. Every other spacing form
  (`SPACING ... RANGE`, `ENDOFLINE`, `SPACINGTABLE`, etc.) is kept verbatim in
  `layer_extra`, not interpreted, in this slice.
- Non-routing layers (`CUT`, `MASTERSLICE`, `OVERLAP`, ...) become `layer` rows
  with their `type`; statements that do not map to columns go to `layer_extra`.
- Each layer's full original text, comments included, is kept in
  `layer.lef_text` and is available as `.lef_text`. This preserves the `#` rule
  IDs (`# Hx.W.1`) without modeling them.
- Top-level statements and blocks the parser does not model (`BUSBITCHARS`,
  `DIVIDERCHAR`, `VIA`, `VIARULE`, `SITE`, `NONDEFAULTRULE`,
  `PROPERTYDEFINITIONS`, `MACRO`, ...) are stored verbatim in `tech_extra`, with
  one warning per kind naming the first line number. Later slices model them as
  needed.

## 6. `get_db`

### 6.1 Objects and handles

Objects are identified by Cadence-style handles: `<type>:<name>`.

| Object | Handle | Notes |
|---|---|---|
| tech | `tech` | singleton, no name part |
| layer | `layer:IA` | |

Handles are plain Tcl strings, so they can be stored in variables and passed
between commands.

### 6.2 Forms the user specified

```
get_db tech
```
Prints the entire tech information: lef_version, db_units,
manufacturing_grid, file, then every layer with every attribute (including
`extra`). This form is the user's explicit requirement and differs from Innovus,
where `get_db` on an object returns its handle; Innovus would use
`report_obj` for this. Return value: the string `tech`, so it still composes.

```
get_db tech.layer
→ layer:H1 layer:H2 layer:G1 layer:G2 layer:IA layer:IB
```
A Tcl list of handles in LEF order.

```
get_db [get_db tech.layer -if {.name == IA}] .min_width
→ 0.36
```

### 6.3 General grammar

```
get_db <root_or_path> [-if {<expr>}]
get_db <handle_list> <.attr> [-if {<expr>}]
get_db <handle_list> .*
```

- `<root_or_path>`: `tech` or a dotted path from it (`tech.layer`). Unknown
  path → error.
- `<handle_list>`: one handle or a Tcl list of handles. A handle for an object
  that does not exist → error naming the handle.
- `.attr`: returns the attribute value for each object. One object → a scalar;
  several → a Tcl list in input order. An empty attribute returns an empty
  string (one object) or an empty list element.
- `.*`: lists every attribute name and value for each object.
- Attribute values that are objects return handles (for example
  `get_db layer:IA .tech` → `tech`).
- Numbers print in the shortest form that round-trips (`0.36`, not
  `0.360000`), matching how Innovus prints.

### 6.4 `-if`

- Braced form `-if {.name == IA}` is the Cadence form.
- The parenthesized form the user typed, `-if (.name == IA)`, arrives in Tcl as
  separate words. `get_db` rejoins the words after `-if` until the closing `)`
  and treats the result as the expression. Both forms behave identically.
- Operators: `==`, `!=`, `<`, `>`, `<=`, `>=`, `&&`, `||`, `!`, parentheses.
- `==` and `!=` on strings use glob matching (`.name == G*`).
- Numeric comparison when both sides parse as numbers, string comparison
  otherwise.
- An unknown attribute in the expression → error.

## 7. Other commands

### `read_tech -file <path>`
- Required `-file`. Missing option, missing file or parse error → error with
  file name and line number. A parse error leaves the database unchanged.
- If tech data already exists, it is replaced and a warning is printed.
- Prints a summary: file, LEF version, DB units, layer count.

### `write_db <path>`
- Saves the in-memory database to `<path>` with the SQLite backup API.
- Refuses to overwrite an existing file unless `-overwrite` is given.

### `read_db <path>`
- Loads a database written by `write_db` into memory, replacing the current
  one. Checks `meta.schema_version`; mismatch → error.

### `man <command>` and `help`
- `man <command>` prints that command's manual page in the shell.
- `help` lists all commands with a one-line description.

### `exit`
- Leaves the shell. No prompt to save in this slice.

## 8. CUI shell

- Python 3.11 in `htree_version4/.venv`, with a real Tcl 8.6 interpreter
  embedded through `tkinter.Tcl()` (no window). Commands are Python functions
  registered with the interpreter, so Tcl variables, `foreach`, `if`, command
  substitution `[...]` and `source <file>` all work.
- Interactive mode: `htree4` shows an `htree4>` prompt with readline history
  and line editing. Multi-line input continues until braces balance.
- Tab completion (user request, 2026-11-07): command names; for `get_db`,
  path segments (`get_db .<tab>` gives `tech`, `get_db .tech.<tab>` gives its
  attributes such as `layer`), layer handles, `.attr` words and `-if`
  attributes, driven by `objects.ATTRS` and `objects.RELATIONS`; file names
  for other commands. Lists show on the first <tab> (Innovus behavior).
  `get_db` accepts a leading dot on paths so completed words run as typed.
- Batch mode: `htree4 -init <script.tcl>` runs the script, then stays at the
  prompt; with `-batch` it exits after the script.
- Messages use an Innovus-like format with tool-specific IDs:
  `**ERROR: (HT4-<nnn>): <text>`, `**WARN: (HT4-<nnn>): <text>`. Errors raise a
  Tcl error so `catch` works and batch scripts stop.

## 9. Manual pages

- One Markdown file per command under `docs/man/<command>.md`, with sections:
  NAME, SYNOPSIS, DESCRIPTION, OPTIONS, RETURN VALUE, EXAMPLES, ERRORS, SEE
  ALSO.
- `man <command>` reads the same file, so there is one source.
- A test fails if any registered command lacks a manual page.

## 10. Project layout (user's layout: one file per command)

```
htree_version4/
  core/htree_builder.py   # main: Tcl embedding, REPL, -init/-batch, dispatch
  core/commands/          # one module per command (NAME, SUMMARY, run)
    get_db.py read_tech.py write_db.py read_db.py man.py help.py exit.py
  core/db.py              # SQLite schema, load_tech, write/read
  core/lef.py             # tech LEF parser (pure)
  core/objects.py         # handles and attributes
  core/expr.py            # -if expression parser
  core/options.py         # -option parsing
  core/messages.py        # ERROR/WARN formatting
  docs/man/*.md           # one manual page per command
  tests/                  # pytest; tests/data/tech.lef is a fixed copy
```

Run: `.venv/bin/python core/htree_builder.py [-init script.tcl] [-batch]`.
`exit` is a tool command because Python's embedded Tcl removes the built-in.

## 11. Testing

- pytest, headless, no Tcl prompt needed.
- Parser tests against `tech.lef` and small inline LEF snippets (single-value
  PITCH, unknown statement, unknown block, malformed line).
- `get_db` tests for each form in section 6.2, `.*`, `-if` with each operator,
  both `-if` syntaxes, bad handle, bad attribute.
- Round trip: `read_tech` → `write_db` → new session → `read_db` → identical
  `get_db tech` output.
- Every registered command has a manual page.

## 12. Decided by the user

- CUI first, GUI later on the same database.
- Data stored in SQLite.
- Commands: `read_tech -file`, `get_db`, `write_db`.
- `get_db` follows Cadence exactly: handles like `layer:IA`, `.name` gives `IA`.
- `get_db tech` prints all tech information.
- `get_db tech.layer` returns all layers.
- A manual is written as commands are built.
- Dependencies live in `htree_version4/.venv` (created, Python 3.11.4).

## 13. Calls made by Claude (user to check)

- In-memory database, saved only by `write_db` (Innovus model).
- Added `read_db`, `man`, `help`, `exit`.
- `get_db` accepts the user's forms and the Innovus aliases (`layers`,
  `head.layers`, chained `layers.name`) and a name-pattern second word
  (`get_db layers G*`).
- Embedded Tcl through `tkinter.Tcl()`.
- Nothing dropped: unmodeled statements kept verbatim (section 5.3), full
  layer text with comments kept in `.lef_text`, plain `SPACING` fills
  `.min_spacing`.
- `write_db` refuses to overwrite without `-overwrite`.
- Glob matching on `==` in `-if`.
- Message ID prefix `HT4`.
- Attribute names in section 5.2. These need checking against Innovus
  `get_db layer:<name> .*` output so they match Cadence exactly.

## 14. Open

- IB layer: resolved, the user added it to `tech.lef`.
- Min spacing source, since `tech.lef` has none.
- Exact Innovus attribute names for layer objects (section 13).

## 15. Slice 2: `read_lef` (user requests, 2026-11-07)

- `read_lef -file <cell.lef>` adds a cell LEF to the physical library.
- User asked for: per cell CLASS, SIZE x y, SITE; per pin DIRECTION, USE, and
  PORT shapes with their layers. Shapes on all layers are read; only layers
  in tech are used in calculations, and `read_lef` reports the others
  (HT4-064). `get_db .lib_cell` lists the cells and pins are reached from
  them.
- Objects: `library_physical` (singleton) -> `lib_cell:<cell>` ->
  `lib_pin:<cell>/<pin>` -> `lib_port:<cell>/<pin>/<n>` ->
  `layer_shape:<cell>/<pin>/<n>/<k>`. `ref_name` is the MACRO name (user's
  term). Attributes are listed in `docs/man/read_lef.md`.
- Tables: `lef_file`, `lib_cell`, `lib_pin`, `lib_port`, `layer_shape`,
  `lib_extra`, `lef_extra`. Schema version 3; older files are refused by
  `read_db`.
- Calls made by Claude (user to check): `lib_port` and `layer_shape` as
  objects (one per PORT, one per RECT/POLYGON); `.rect` is the normalized
  bounding box, also for polygons; `.in_tech` is evaluated at query time;
  `.direction` holds the Cadence value (in, out, inout, feedthru; user
  request 2026-11-07), with `DIRECTION OUTPUT TRISTATE ;` kept in `.extra`; `.class` keeps the subclass (`pad inout`); OBS is not
  modeled yet (kept in `.lef_text`); repeated `read_lef` appends and a
  duplicate MACRO keeps the first definition (HT4-062); tech data is not
  required to read a cell LEF.
- `get_db -if` (user report, 2026-11-07): filters the objects at the end of
  the attribute chain, as Cadence does. Before, it filtered the input
  objects, so `get_db <cells> .lib_pins -if {.direction == out}` failed.

## 16. Slice 3: `read_spine_spec` (user request, 2026-11-07)

- `read_spine_spec -file <yaml>` reads spine specs; what to build from them
  comes later. `get_db spine_spec` lists all specs.
- Objects: `spine_spec:<spec>` -> `spine_level:<spec>/<L>` ->
  `spine_cell:<spec>/<L>/<cell>`. Key-to-attribute map in
  `docs/man/read_spine_spec.md`.
- A file holds several specs as `---`-separated documents or a list under
  `spine_spec:`. Duplicate keys are an error (PyYAML would silently keep the
  last, merging two specs). The user's first `runs/custom_spine.yaml` had
  this problem.
- Dependency: PyYAML 6.0.2. Schema version 4.
- Calls made by Claude (user to check): flattened attribute names
  (`stubs.count` -> `stub_count`); unknown keys kept in `.extra`; re-reading
  a spec name replaces it (HT4-082); values stored as written, no derived
  values (stub length) and no cross-checks yet.

## 17. Slice 4: `read_def` (user request, 2026-11-07)

- `read_def -file <def>` reads only the boundary (DIEAREA) and PINS; all
  other sections are skipped and counted. Example input: cf999.def
  (G0857_pnr inputs, 45 MB, 110,728 pins, 26-point rectilinear DIEAREA).
- Objects: `design:<d>` -> `port:<d>/<pin>` -> `port_shape:<d>/<pin>/<k>`
  (Cadence names: top-level pins are ports). Coordinates in microns; pin
  shapes absolute (orientation applied, checked: all 110,725 cf999 shapes
  fall inside the die polygon).
- Pin layers not in tech are reported (HT4-093), as for read_lef.
- Tables: `design`, `port`, `port_shape`, `port_extra`. Schema version 5.
- Calls made by Claude (user to check): `port` naming; one design per
  database (re-read replaces); status/location/orient from a pin's first
  PORT; skipped sections are not stored at all (user: "rest not needed");
  `.gz` input supported; `get_db design` prints a summary.
- TRACKS added (user request, 2026-11-07): each statement is a
  `track_pattern:<d>/<k>` (Cadence name) with direction x|y, start,
  num_tracks, step, end, mask, same_mask, layers. Inline '#' comments after
  ';' are ignored. Schema version 6. Noted: cf999 D12 tracks start at 0.038
  while the tech LEF D12 OFFSET is 0; list attributes compare as whole text
  in -if (open question whether == should match any element).

## 18. GUI, first version (branch create_gui, user request, 2026-11-07)

- User: PySide6 (PySide6-Essentials 6.9.3); `gui_show` opens the GUI and the
  terminal stays usable; a layout canvas; a right-side panel with checkboxes
  to show or hide nets, layers, cells, spine and ports; all GUI code in
  `core/gui/`. v3 (PyQt5) was used as reference for the canvas (y flip,
  wheel zoom, clipped track painting) and the visibility panel.
- How the terminal stays usable (Claude's call, spiked first): one thread;
  a PyOS_InputHook runs the Qt event loop while readline waits for input.
  The Tcl interpreter and SQLite connection are only used from that thread.
  The window refreshes after any command that changes the database
  (detected with sqlite total_changes and the connection identity).
- Canvas: boundary polygon, port shapes coloured by layer, tracks painted
  behind shapes, clipped to the boundary, only when lines are at least 4 px
  apart. Wheel zoom about the cursor, left drag pans, F fits, click selects
  the nearest port shape within 3 px and prints it in the terminal and the
  status bar (Claude's call; the user had not said what a click does).
- Panel: Objects (Boundary, Ports, Tracks, Nets, Cells, Spine; categories
  with no data are disabled and unchecked: nets, placed cells and spine
  geometry do not exist yet) and Layers (tech layers first and checked,
  non-tech layers marked * and unchecked; All / None / Tech only).
- gui_show checks the display in a child process first, because Qt aborts
  the whole process (losing the in-memory database) when it cannot connect.
- Measured on cf999 (offscreen): gui_show 2.0 s with 110,725 shapes; full
  view repaint about 0.1 s.
- Panning fix (user report, 2026-11-07): dragging stopped with the design at
  the window edge, because QGraphicsView only scrolls inside its scene rect
  (v3 had the same issue and padded by one design size, which locks again
  when zoomed out). Now the scene rect is the design padded by 10 design
  sizes per side and zoom-out stops when the design is 20 px across, so the
  padded area never fits in the window. Scrollbars are hidden; pan by drag.
- Selection (user request, 2026-11-07): select ports, nets and instances in
  the GUI; `get_db selected` returns them. Selection is session state
  (`Database.selection`, not saved by write_db, stale handles dropped).
  Click / Ctrl+click toggle / Shift+drag area / click on empty clears.
  Claude added `select_obj` and `deselect_obj` (Cadence names) so the
  terminal can drive the same selection; the highlight follows. Nets and
  instances: nothing in the database yet (cf999.def has no COMPONENTS or
  NETS); open question where they will come from.
- Menu bar and toolbar (user request, 2026-11-07): toolbar buttons Zoom
  Selected and Blink Selected (user); Fit button and the menu contents
  (File / View / Select) are Claude's calls. Zoom Selected shows at least
  5 um; Blink also flashes a marker at least 30 px across (Claude's calls).
- Hardening: exceptions in after-command hooks are reported as HT4-999
  instead of failing the command.
- Mouse map changed (user request, 2026-11-07): left drag zooms to the box
  drawn; Shift+drag selects all objects with a shape fully inside the box
  (user: "within the bbox", "multiple objects can be selected"). Panning
  moved to middle drag and arrow keys (Claude's call: left drag is taken).

## 19. `assign_track_for_route` (branch create_spine, user request, 2026-11-07)

- `assign_track_for_route -net {VDD_SOC, -, VSS, -} -layer IA`: track 1
  VDD_SOC, 2 signal, 3 VSS, 4 signal, then repeat (user's definition).
- Claude's calls (user to check): tracks are the DEF patterns in the
  layer's tech direction (horizontal -> TRACKS Y, vertical -> TRACKS X),
  numbered from the lowest coordinate, several patterns merged; tracks
  outside a rectilinear boundary still count; commas optional; layer must
  be in tech; nets checked against port nets (warning); stored as a rule
  per layer (`track_assignment` table, schema 7), saved by write_db,
  re-run replaces; object `track_assignment:<layer>` with `.tracks`
  ({coordinate net} pairs) and `.counts`.
- cf999 IA: 19,645 tracks, y 0.36 + 0.72 n; VDD_SOC 4,912, VSS 4,911,
  signal 9,822.
- GUI (user request, 2026-11-07): a dropdown next to Tracks shows each
  layer's assignment and a checkbox per "track segment", read by Claude as
  one per net of the pattern (VDD_SOC, VSS, signal), not per track (19,645
  on IA). Assigned tracks drawn in net colours (signal grey dotted), only
  when lines are at least 4 px apart, clipped to the boundary.
- GUI tracks (user request, 2026-11-07): tech layers show only tracks in
  their preferred tech direction (IA horizontal: TRACKS Y only). Claude's
  calls: the database keeps every DEF pattern (get_db unchanged); layers
  not in tech have no direction and show all tracks.
- Ruler (user request, 2026-11-07): toolbar button next to Blink Selected
  with a side dropdown: Orthogonal / Diagonal, and "Snap to nearest object
  edge" that only snaps to objects shown in the GUI. Claude's calls:
  orthogonal = held horizontal or vertical by the larger mouse delta;
  diagonal also shows dx/dy; snap radius 10 px; snap targets are visible
  port shapes, the boundary when shown, and drawn tracks (track drawing and
  snapping share one function, so they cannot disagree); snap on and
  orthogonal by default; rulers persist until Clear Rulers; result printed
  in the terminal; right click / Esc cancel. Checked on cf999: two clicks
  0.004 um off two D12 pin edges measured 18.313 um, the exact gap.
- NA in track patterns (user request, 2026-11-07): `NA` means the track is
  left blank, not used for anything. Reserved like '-'; not checked as a
  net; listed last; GUI checkbox "blank (NA)" starts unchecked and draws
  dim dashed lines (Claude's calls).

## 20. `create_inst` (branch create_spine, user request, 2026-11-07)

- User: `create_inst -ref_cell <cell> -location {x y}`; example location
  {5622.772 10066.7} on cf999.
- Claude's calls (user to check): location = lower-left of the placed bbox
  (DEF convention) for every orientation; optional -name (default inst_N)
  and -orient (default N); errors for unknown cell / no SIZE / duplicate
  name; warnings for outside boundary, overlap with another instance
  (touching is fine), off manufacturing grid; no row/site check (ROWs are
  not read); object `inst:<name>` with ref_name, lib_cell, location,
  orient, bbox, status; table `inst` (schema 8), saved by write_db.
- GUI: instances drawn as an outline plus the cell's pin shapes in layer
  colours (pins follow layer visibility), under "Cells (instances)";
  selectable by click, Shift+drag and select_obj (covers the earlier
  "select instances" request).
- Fixed: rebuilt panel lists painted stale checkboxes until deleted.
- Pins and labels (user requests, 2026-11-07): a "Pins" checkbox for
  instance pin shapes (Cells now only the outline) with a "Label" checkbox
  that writes pin names at shape centres (instance pins and ports; drawn
  in screen pixels; none when more than 2000 in view). Clicking a shown
  instance pin selects that pin, not the instance: new object
  `pin:<inst>/<pin>` (Cadence name) with inst, lib_pin, direction, use,
  layers, rect; `inst .pins`. Picking fixes found on the way: hit tests
  use shape geometry (an L-shaped polygon's bbox and the 2-unit highlight
  pen used to swallow clicks); ties go to the shape on top when under the
  cursor, to the larger shape on near misses (zoomed out: the instance);
  Shift+drag over a whole instance selects the instance only.

