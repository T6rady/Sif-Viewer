# SIF Viewer 1.4.4

A read-only Windows desktop viewer for contract furniture `.sif` files. Built
with Python 3 and PySide6. Opening a file never writes to that file. CSV export
writes a separate file. Reversible CSV conversion can create a separate SIF;
in-place SIF editing and comparison are unavailable. The installed application
works offline and makes no network requests.

## Run on this computer

The project-local `.venv` already contains the dependencies. From this folder:

```powershell
.\.venv\Scripts\python.exe main.py
```

The supplied SIF artwork in `assets/app.ico` is used for the window and taskbar
icon and embedded into the executable for File Explorer and desktop shortcuts.
The same icon is used when running from source or from the packaged application.

To open the supplied example directly:

```powershell
.\.venv\Scripts\python.exe main.py 'C:\path\to\example.sif'
```

Alternatively run `run.ps1`, or double-click `dist\SIF Viewer\SIF Viewer.exe`
after building. The executable does not require a separate Python installation.

## Set up on another Windows computer

Install 64-bit Python 3.10 or newer (tested with Python 3.12 on Windows 11).
Open PowerShell in the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Dependency installation needs Internet access or pre-downloaded wheels; using
the viewer afterward is entirely offline. Virtual environment activation is
unnecessary. `requirements.txt` pins the tested PySide6 and PyInstaller versions.

## Using the viewer

- **Set default .sif app…** below the file name explains the steps and opens
  **Windows Settings → Apps → Default apps**. Search for `.sif` and choose
  **SIF Viewer**. On Windows 10, choose **Choose default apps by file type** first.
  Install the 1.4.1 or newer Setup first so SIF Viewer appears as an available
  app; portable/source copies do not register themselves. The button works
  before opening a file. If Settings cannot open, the app shows manual steps.
  Windows requires your final choice; the installer does not replace an existing
  default automatically. After selection, double-clicking a `.sif` launches the
  viewer with that file, including paths containing spaces.
  The button hides automatically when Windows reports SIF Viewer as the current
  default. This is checked at startup and when returning to the viewer, including
  after changing Windows Settings. It reappears if another app becomes the
  default; if the association cannot be checked, the button remains available.
- **Open File** / **Ctrl+O** opens the file dialog. You can also drop one local
  `.sif` file anywhere on the window. The full path is selectable below the name.
- The compact header shows the file name, path, and read-only badge. **Copy path**
  copies the full file path; the folder button opens its containing folder.
- **Raw text** shows all decoded text in source order, including blank lines,
  tabs, leading and trailing spaces, and values containing `=`. Line numbers,
  both scrollbars, selection, Ctrl+C, and **Word Wrap** are supported.
- **Ctrl+F** focuses the current view's search field. In **Table**, typing filters
  products by source values including product number, description, options,
  attributes, and uninterpreted fields. Filtering is literal, with **Aa** to match
  case. Counts and totals follow the filtered records. In **Raw text**, Enter,
  **Next**, **Previous**, **F3**, and **Shift+F3** search original text with wraparound.
- **Table** is the default view for supported SIF files. Click a heading to sort; quantities
  and prices (including calculated extended list prices) sort numerically.
  Drag heading dividers to resize columns and drag headings to reorder them. Select
  cells and press Ctrl+C to copy tab-separated values. Hover over a cell for its
  full value and the product's source line. Horizontal scrolling reveals options
  and additional columns. Products with missing or blank fields are highlighted
  in amber. The attention badge selects an affected item and the details panel
  explains its warnings. The **Missing / blank fields** column remains available
  through Columns. Warnings retain original item numbers after filtering and sorting;
  relevant source lines are highlighted in Raw text.
- **Columns** in Table View lets you show/hide each column, **Show all columns**,
  or **Reset columns** to the default selection and order. Explicit visibility
  choices carry across files during the current session. The compact defaults are
  manufacturer, product number, description, option count, quantity, list price,
  extended list, sell discount, and buy percentage. Extra supported fields can be shown as blank columns.
  Options and attributes have separate code and description columns, with all
  repeated values kept in source order and separated by ` | `. Combined columns
  remain available in the menu. Ctrl+C copies visible columns in their displayed order.
- Selecting a row opens its full description and all option/attribute pairs in
  the right-hand details panel. **Copy all** copies a section as text; **View raw
  text** jumps to that item's source record. The panel can be resized with the
  divider. Arrow keys navigate items; Enter focuses details.
- **Hide details** beside Columns, **Hide** inside the panel, or **Ctrl+D**
  collapses the details panel to give the table more room. **Show details**
  restores it at its previous width. Enter on a table item opens its details.
  Selecting another item, filtering, changing views, and opening another file
  leave a collapsed panel hidden until you reopen it.
- **Dark mode / Light mode** in the top header switches the entire viewer,
  including raw text, line numbers, options, menus, and warnings. Your theme and
  details-panel visibility are remembered between launches in per-user Windows
  settings. Neither preference changes the opened SIF file.
- The footer totals visible quantities and extended list prices with exact decimal
  arithmetic. An asterisk marks incomplete totals when any contributing source
  values are missing; hover for the missing counts. Missing data is never zero-filled.
- **Currency** starts at **Not set** for each new file. Choosing USD, CAD, EUR, or
  GBP adds a display label only: there is no exchange-rate conversion and no
  currency is inferred from the SIF. Prices are presented to two decimal places;
  tooltips, raw text, copied cells, and source values retain their exact precision.
- Uninterpreted fields are hidden from the compact table by default. Click the
  information badge to show their source-code columns, or inspect them in details.
- **Export CSV…** / **Ctrl+Shift+E** in Table View exports all filtered rows and
  visible columns in the current sort and column order. Original item numbers
  are included in the first column; full descriptive column headings include
  SIF field codes. The totals row and hidden columns are omitted. Show option
  code/description columns through Columns before exporting if you want those
  values instead of just their count. A pending filter is applied before export.
  The Save dialog lets you choose the destination and confirm replacement of an
  existing CSV. The opened source and any `.sif` destination are protected.
- CSV values retain full source precision, trailing spaces, and blank fields.
  Calculated extended list prices use exact decimal multiplication. Currency
  display labels and screen-only price rounding are omitted. Standard CSV quoting
  handles commas, quotes, and embedded line breaks; files use UTF-8 with a BOM
  and Windows line endings. Excel may automatically interpret product numbers,
  dates, or formula-like text: use its text/CSV import with text column types to
  retain text identifiers such as leading-zero product codes.
  Repeated option/attribute values use the same ` | ` separators as the table.
  This is a readable table export; it does not support reconstructing a SIF.
  Export runs in the background from a snapshot, so later table changes do not
  change the file being exported. Failed or cancelled exports leave an existing
  CSV intact and remove their temporary file.
- The status bar shows file name, byte size, physical line count, parsed product
  count (when available), and encoding. Hover for line-ending style and full path.

Raw View is a text display: Qt renders CRLF, LF, and CR as line breaks and clipboard
text uses the widget's newline representation. The reader retains the exact
decoded string and original line endings in memory; no source bytes are rewritten.
A final line break creates an extra empty editor row; the status count excludes
that trailing empty row. Encoding BOMs are metadata, not visible text content.

## Reversible SIF / CSV conversion

The **Convert…** menu provides two separate actions:

- **Export reversible CSV…** exports the complete loaded text snapshot, even
  when Table View is unavailable. Filtering, sorting, hidden columns, calculated
  prices, and currency labels do not affect this export. The suggested name is
  `filename.sif.csv`. The existing **Export CSV…** remains the readable table export.
- **Convert CSV to SIF…** accepts only the reversible format below and suggests
  `filename-converted.sif`. It works without opening a SIF first. A successful
  conversion opens the generated file so you can inspect its table, raw text,
  encoding notice, and item warnings. Unsupported table syntax stays unsupported;
  literal text preservation does not introduce new SIF interpretations.

Conversion runs in a worker thread. Opening another SIF and starting another
export/conversion are disabled during conversion. Closing cancels pending work.
The opened SIF and source CSV are protected, including hard-link and symbolic-link
aliases. A Save dialog confirms replacement of other existing destinations.
Only a complete, validated conversion replaces its destination; failure or
cancellation preserves an existing destination and removes temporary files.

### CSV format `ori-sif-csv/1`

The CSV uses UTF-8 with a BOM, standard CSV quoting, and CRLF CSV record endings.
All values are text. Its six exact column headings are:

```csv
kind,sequence,item,code,value,eol
meta,,,format,ori-sif-csv/1,
meta,,,encoding,utf-8,
meta,,,bom,none,
field,1,,SF,Example,CRLF
field,2,,ST,,CRLF
field,3,1,PN,000123,CRLF
field,4,1,MC,,CRLF
field,5,1,ON,F01,CRLF
field,6,1,OD,"Blue, woven",CRLF
field,7,1,AN,NOTE,CRLF
field,8,1,AD,,CRLF
field,9,1,PS,001.2300,CRLF
field,10,1,PS,,NONE
```

This abbreviated example intentionally lacks several standard fields. They
remain missing and produce item warnings rather than being invented on import.

- `kind=meta` contains file metadata: `format`, `encoding`, and `bom` are each
  mandatory and unique. Optional `encoding_note` retains the reader's legacy
  encoding ambiguity notice. Metadata has empty sequence, item, and eol cells.
- `kind=field` contains one exact `CODE=VALUE` line, split at the first equals
  sign. Unknown codes and every repetition are retained in source order. Each
  `ON`, `OD`, `AN`, and `AD` has its own row; no delimiter combines their values.
- `kind=text` contains an entire non-field line in `value`, with an empty `code`.
  This includes empty lines, whitespace-only lines, and unsupported literal text.
  A syntactically valid field cannot be disguised as a text row.
- `sequence` is a unique positive integer. Import sorts by this number and
  requires contiguous numbers starting at 1. CSV row order itself is irrelevant.
  Inserting or deleting a SIF line requires renumbering the remaining sequences.
- `item` is the original item number in source order, determined by exact `PN`
  boundaries. It is empty before the first product and is checked on import.
  Changing product boundaries requires updating item references. It is never
  written into the generated SIF as an extra field.
- `value` preserves empty text, spaces, tabs, identifiers, decimal spelling,
  quotes, commas, equals signs, and literal ` | ` text. A blank field has a row
  with an empty value; an absent field has no row. In particular, blank `MC`
  stays blank. Data cells cannot contain CR or LF; each physical SIF line must
  have a separate row.
- `eol` is the original SIF line ending: `CRLF`, `LF`, `CR`, or `NONE`. Only the
  last SIF line may use `NONE`. There is no extra fictitious row after a final
  newline. An empty SIF has metadata only.

Encoding is one of `utf-8`, `utf-16-le`, `utf-16-be`, `utf-32-le`, `utf-32-be`,
or `cp1252`. BOM is `present` or `none`; UTF-16/32 requires `present`, and cp1252
requires `none`. Windows-1252 remains an assumption, not a verified detection.
Conversion rejects characters that cannot be encoded; it never substitutes
replacement characters. Untouched reversible CSV reconstructs the source SIF
byte for byte, including BOM, mixed line endings, and final-newline state.

The SIF limit remains 64 MiB. Reversible CSV is limited to 256 MiB in both
directions; its additional rows and metadata can make it larger than the SIF.
An export exceeding that limit fails without replacing its destination.
CSV structural errors block conversion. Missing SIF fields remain warnings;
existing parser rules continue to control Table View availability.

**Excel editing:** import the CSV with all columns treated as text. Opening CSV
directly may change leading zeros, dates, precision, or formula-like values;
quoting alone cannot prevent Excel's automatic interpretation. The importer
does not evaluate formulas or repair values that a spreadsheet changed.

## Supported SIF interpretation

The parser supports a deliberately conservative subset of the line-oriented
standard furniture SIF dialect described in the vendor's
[Design Manager SIF specification](https://knowledge.designmanager.com/support/solutions/articles/22000201116--sif-file-specification).
This is not a universal parser for every format named SIF.

Each nonblank line is `CODE=VALUE`; only the first `=` separates the code from
the value. An `SF` or `ST` header is required. Each `PN` starts a product. The
standard expects `PD`, `MC`, `QT`, and `PL` fields, but missing or empty product
fields produce warnings rather than blocking the table. Their cells remain blank;
no values are filled in or guessed. Nonblank quantities and list prices must be
plain decimal numbers to participate in calculations. Other numeric text remains
visible with an item warning; it does not prevent the table from opening.
The UI preserves source spelling and assumes no
currency. `MC` is the source manufacturer/vendor **code**; it is never expanded
into a guessed company name.

Verified optional fields include `TG`, `S-`, `S%`, `P%`, `B%`, and `PV`.
`GC` is shown as catalog / product line code, following the manufacturer's
[Herman Miller Order SIF mapping](https://apidev.hermanmiller.com/om/quotetool/Content/HermanMillerQuoteTool040500OrderSIFMapping.pdf).
Options are repeated `ON`/`OD` pairs; attributes are repeated `AN`/`AD` pairs.
Their order and values are retained. Percentages are displayed as supplied.
**Extended list price (calculated)** is exact decimal `QT × PL`, without
rounding or currency assumptions. Missing quantity or list price leaves the
calculation blank; a supplied zero remains zero. Source fields are unchanged.
Customer/dealer prices, margins, taxes, option pricing, and additional tag fields
are not inferred from another application's screenshot. Picture paths are plain text
and are never opened, executed, or fetched.

Unknown codes are exposed in individual columns such as **PS (uninterpreted)**
and **WT (uninterpreted)** when present in the file, including repeated values.
The combined **Uninterpreted fields** column remains available through Columns.
The app does not assign these codes unverified semantic names. For example,
`PS` is not labelled customer or dealer price without a verified dialect mapping.
Missing or blank product fields are called out by item number in original file
order. Those item numbers stay attached to their products after sorting. Raw
text line numbers are explicitly labelled and shown only in tooltips: an empty
field identifies its exact raw text line; an absent field points to the product's
starting raw text line. Both relevant lines are highlighted in Raw View. All
products remain visible.

Repeated product fields are supported, preserving every value in source order.
Their columns display values separated by ` | `; reversible CSV retains each
original field separately. Conflicting repeated numbers are excluded from
calculations and flagged, rather than choosing a quantity or price.
Extra fields before the first product are retained as file metadata without
guessing their meanings. Field codes may start with digits, including `3D`.
These variations cover the supplied HON, KI, Riverbend, hospital, and other
furniture exports without adding a special rule for each filename.

Version 1.4.4 was checked against all 20 available sample SIF files, including
opening every file sequentially through the application window. The table
row counts match every source `PN` boundary, and each file survives a byte-identical
reversible CSV round trip without changing its source hash or modification time.
The additional samples include `01579293-B.sif` (24 products),
`15916_Russel Hospital BID.sif` (37), `Hon sif file.Sif` (47), `KI sif.sif` (50),
and the Riverbend workstations export (80). Private source files are not bundled.

If pairs are broken, headers are misplaced, or line structure
is unsupported, the entire table is unavailable with a specific reason.
Raw View stays available; no partial table pretends the file was fully parsed.

To extend support, add documented scalar definitions to `FIELD_DEFINITIONS` in
`core/sif_parser.py` and add tests. Header and repeating-pair variants require
explicit parser changes. Unsupported dialects should keep their Raw View fallback.

## Encodings and limits

- ASCII / strict UTF-8, UTF-8 BOM, and BOM-marked UTF-16 / UTF-32 are supported.
- Windows-1252 is the strict fallback for non-UTF-8 legacy text. It is labelled
  **assumed**, with an ambiguity notice. Other legacy encodings cannot be
  reliably inferred. There is no replacement-character decoding.
- NULs, binary control characters, invalid BOM-marked Unicode, and unsupported
  encodings produce useful errors. Unmarked UTF-16/32 is rejected. No detector
  can distinguish every printable byte sequence from text.
- Empty files open normally; the table explains that there are no records.
- The V1 file limit is **64 MiB** to bound memory use. Reads and parsing run in
  a worker thread; text is added in 32 Ki-character GUI chunks. The table uses
  a model rather than allocating a widget per cell. Loading is sequential;
  opening another file is enabled after the current load finishes.
- A failed open leaves the previous successfully loaded document visible.
  Closing during a read hides the window and lets the worker finish safely.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The 88 tests cover reading, BOMs, exact whitespace, line endings, legacy
encoding notices, binary and malformed input, limits, parser boundaries,
verified fields, unknown fields, pair validation, decimal sorting, opening,
dialog wiring, drag and drop events, search, copying, metadata, and read-only
behavior. GUI integration tests use Qt's offscreen platform.
Missing and empty field checks verify that products remain visible, cells stay
blank, warnings retain source line numbers through sorting, raw highlights do not
interfere with search, and loading a clean file clears prior warnings.
Additional checks cover split option/attribute fields, repeated uninterpreted
values, column visibility/reset/reload, copying in visible column order, exact
extended prices, missing operands, and sorting calculated prices numerically.
Redesign checks cover literal/case-sensitive filtering, matching totals and
details, keyboard navigation, every option pair, raw-record navigation, monetary
formatting without source mutation, and partial/high-precision totals.
CSV checks cover quoting, Unicode, exact values, repeated fields, original item
numbers, filtering, sorting, reordered columns, cancellation, source aliases,
failed writes, destination replacement, and background snapshot isolation.
Reversible conversion checks cover byte-identical reconstruction across supported
encodings and BOMs, empty files, mixed endings, absent versus blank fields,
repeated options/attributes/unknowns, reordered CSV rows, strict metadata and
item/sequence validation, oversized fields and limits, source aliases, atomic
failure/cancellation, GUI dialogs, generated-file warnings, worker responsiveness,
and closing during conversion. Three private-file tests are skipped unless
`SIF_TEST_FILE` is set.
Default-app UI checks verify the Settings launch, manual fallback, and unchanged
opened SIF. Installer checks also verify the quoted SIF open command, Open With
and Default apps registration, cleanup, and preservation of existing defaults.

To include a real private SIF file without copying it into the repository:

```powershell
$env:SIF_TEST_FILE = 'C:\path\to\example.sif'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The three private-file tests are skipped when `SIF_TEST_FILE` is absent. For
1.4.0, all 80 tests passed with the supplied `KQ163504.sif`: 1,674 bytes, 122 CRLF-terminated lines,
ASCII / UTF-8, four products, and 41 option pairs. `PS` and `WT` are retained
as uninterpreted fields. The original SHA-256 and modification time were
unchanged after reading and parsing. The supplied file is not bundled.
Both supplied files also passed byte-identical SIF / reversible CSV / SIF
round trips. Reading, ordinary CSV export, and reversible conversion left their
original hashes and modification times unchanged.

The additional supplied `KQ152346.sif` opens as 42 products. Items 2 and 42
have empty `MC` fields in this SIF copy. Their raw text locations (16 and 786)
are secondary details in tooltips, not item numbers. The table remains available
and the original file stays unchanged.

The automated responsiveness check loads a synthetic 1,080,024-byte file with
20,000 products and checks that all text arrives while a GUI heartbeat keeps
running. This is a practical regression check, not a promise of constant loading
time for every size, line length, machine, or SIF dialect.

The packaged Windows executable was also checked through its visible interface:
launch, native Open File dialog, the supplied file's Raw View and metadata,
four-product Table View, Ctrl+F, and a highlighted `Karman` search result.

## Build the Windows executable

Build on Windows using the same architecture as your target computers:

```powershell
.\build.ps1
```

The script runs the tests, stops on failures, and invokes:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --icon 'assets\app.ico' --add-data 'assets:assets' --name 'SIF Viewer' main.py
```

During packaging, the script temporarily limits its process PATH to the Python
environment and Windows directories. This prevents unrelated third-party DLLs
(such as another tool's ICU library) from being bundled in place of Windows
libraries. It restores the original PATH afterward. Prefer the script for builds.
It uses the Windows temporary directory for intermediate build files and replaces
only this project's generated `dist\SIF Viewer` folder. Close the packaged app
before rebuilding. This also handles read-only directory flags from OneDrive.

If local script execution is restricted, run the two commands (tests and
PyInstaller) directly. No PowerShell policy change is needed.

Output: `dist\SIF Viewer\SIF Viewer.exe`. Distribute the **entire**
`dist\SIF Viewer` folder, including `_internal`, rather than only the executable.
This uses PyInstaller's folder distribution for faster startup and inspectable
dependencies. No installer is required for this portable option. Administrator
privileges and a separate Python installation are
unnecessary on the destination computer. Retain dependency
license notices when redistributing; Qt/PySide6 and PyInstaller have their own
licenses.

## Share the Windows installer

The single-file installer is:

```text
dist\installer\SIF-Viewer-1.4.4-Setup-x64.exe
```

Send that Setup EXE to recipients. They do not need the portable folder, Python,
Inno Setup, or an Internet connection. The `.sha256` file alongside it provides
an optional integrity checksum.

The installer supports 64-bit Windows 10 (build 19041 or newer) and Windows 11.
It installs for the current user, normally to:

```text
%LOCALAPPDATA%\Programs\SIF Viewer
```

It creates a Start menu folder containing SIF Viewer and its uninstaller. A
desktop shortcut is selected by default and may be unchecked during setup.
Shortcuts use the supplied SIF icon and the same taskbar identity as the app.
No administrator access is requested. Re-running Setup updates the same
installation rather than registering another copy.
The installer registers SIF Viewer as an available per-user `.sif` handler with
its icon and a quoted open command. It appears in Windows Default apps and
Open With. Setup preserves the existing default; use **Set default .sif app…**
in the viewer to make your selection. Uninstall removes only SIF Viewer's own
handler entries, preserving other applications' registrations.

To remove it, use **Settings → Apps → Installed apps → SIF Viewer → Uninstall**,
or **Uninstall SIF Viewer** in its Start menu folder. Uninstall removes installed
application files, shortcuts, and the uninstall entry. It does not remove user
SIF files. Files that users add inside the install directory are also preserved.

The installer is not code-signed with an ORI publisher certificate, so Windows
may identify its publisher as unknown. No certificate or signing service has
been purchased or configured as part of this project.

### Rebuild the installer

The installer recipe uses [Inno Setup](https://jrsoftware.org/isdl.php), tested
with version 6.7.3. A project-local compiler is available under `.tools/innosetup`
on this computer. On another build computer, install Inno Setup 6.3 or newer or
pass the path to its `ISCC.exe` explicitly:

```powershell
.\build-installer.ps1
# Repackage an already-built app without rebuilding it:
.\build-installer.ps1 -SkipAppBuild
# Use a compiler in another location:
.\build-installer.ps1 -Compiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

The script reads the app version from `main.py`, gathers dependency license
texts, compiles the Setup EXE, and writes its SHA-256 checksum. Normal builds
first run `build.ps1`, including the application tests. Close the portable app
before rebuilding it. Stable installer identity `ORI.SIFViewer` supports
updating the existing per-user install. The installer source is
`installer/sif-viewer.iss`; all runtime files come from `dist/SIF Viewer`.

For an isolated end-to-end installer check:

```powershell
.\installer\test-installer.ps1
```

This compiles a uniquely named test variant, installs it twice into
`test-artifacts`, checks both shortcut targets and the Windows uninstall entry,
starts the installed app offscreen, then uninstalls the test copy. It also
checks that a user-created `.sif` survives uninstall. Test shortcuts and registry
entries use a unique identity and are cleaned up; logs remain in `test-artifacts`.

## Project structure

```text
main.py                 Desktop entry point and application palette
assets/app.ico          Supplied multi-resolution Windows icon
ui/main_window.py       Toolbar, status, dialogs, drag/drop, worker lifecycle
ui/raw_view.py          Text display, gutter, incremental loading, search
ui/table_view.py        Read-only model, decimal sorting, cell copying
core/file_reader.py     Bounded read-only loading and strict text decoding
core/sif_parser.py      Documented field registry and conservative parser
core/table_data.py      Shared unformatted record values
core/csv_exporter.py    Background-ready CSV writing and source protection
core/sif_csv.py         Reversible CSV schema, validation, and atomic conversion
tests/                  Standard-library unittest + Qt integration checks
requirements.txt        Tested dependency versions
run.ps1                 Project-local launcher
build.ps1               Test then package for Windows
build-installer.ps1     Package the Windows Setup EXE and checksum
installer/              Inno Setup recipe, notices, licenses, and smoke test
```
