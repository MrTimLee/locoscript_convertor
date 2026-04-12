## Locoscript Convertor Project Requirements

# North Star

- A standalone application that allows a user to convert one or more Locoscript 2 file(s) to a different output. The user can select the output from a range of different options. The user can provide an individual file or multiple files.


## Key Requirements
# General
- The application should be standalone and self contained
- The application should require minimal external dependencies to run
- The application should run on a PC or Macintosh
- The application should be performant for large files (+2MB) converting them in less than 30 seconds
- The application will need to convert up to 30 files
- The application will need to convert files of mixed "types"
- The application should be coded in Python
- The application should come with a README and installation instructions for anyone to follow

# UI
- The application will provide a UI from which users can select input files for processing 
- The UI should be a desktop UI
- The application will allow a user to select multiple files for processing at once 
- The application will allow a user to select the output type for a processed document, either plain text, RTF or docx

# Conversion Behaviour
- If processing multiple files the application should run them serially
- If a character cannot be directly mapped to a Unicode equivalent a "?" will be used instead
- Converted files should be saved in the same folder as the input file
- Converted files will be named the same as the input file with the new extension appended (e.g. `BUILDNGS.A-C` → `BUILDNGS.A-C.docx`)
- If during conversion an existing file is found, then the Application should create a prompt asking the user for input
- Where a file already exists a user can chose to skip conversion or overwrite the exiting file. If running a batch, the user can also chose to "skip ALL overwrites" or "Yes to ALL overwrites"
- If a batch conversion is complete a success message is shown with the time taken and the count of files processed
- Files to be converted may have any file extension, or none

# Errors
- If when processing multiple files a file fails, the error should be logged in a .txt file and processing should move to the next file
- The error log should be saved in the same directory as the application
- The error log should be named "DocConvertor-Error.log"
- The error log should be appended to on each run
- An error log entry should consist of: <TIMESTAMP> - <DocumentName>: Full Error Message
- If one or more files fail during a batch run an error message should be shown stating the number failed and directing the user to investigate the error log. 
- If an input file is not recognised as a valid Locoscript 2 format, treat it as a conversion error
- If a successfully converted output file is less than 10% of the size of its input file, log a `[WARNING]` entry to the error log and surface a warning to the user in the completion message. This catches cases where the parser has silently failed to extract most of the document content.



---

# Known Limitations

These are issues that are understood but not yet resolved. They are good candidates for future work.

## First paragraph / document header
Largely resolved. `_find_content_start` now iterates through structural section-header blocks (`22 XX 0b` with B3 ≥ `0x80` and B4 = `0e`, e.g. `c4 0e` in standard files and `a6 0e` in `22 6d` variant files), jumping across any following section break to find the first real content paragraph. This eliminated header junk in 185 of 443 sample files with no regressions. A small number of documents (e.g. those with mixed control bytes inside the first content block) may still show minor artefacts in para[0], but the body of the document is unaffected.

## Running header / footer extraction
Implemented. Headers and footers are now extracted as separate `Paragraph` objects (`doc.header`, `doc.footer`) and rendered appropriately in all three output formats: TXT uses `---` separators, RTF uses `\header`/`\footer` groups, DOCX populates `section.header`/`section.footer`. Confirmed working on HENCOTES (header + footer) and BUILDNGS.H (footer only).

### Page number zone in footers
Footer sections in Locoscript 2 use a two-zone layout: a **centre-aligned page number zone** followed by a **right-aligned document reference zone**. The page number zone is identified by a `11 06` (centre alignment) code followed by a `3d 3d` doubled-pair marker (`==`) and a page-number token sequence. The document reference zone begins after a `10 07` (right alignment) code and contains the human-authored text (e.g. `CND 4.1,  4 Oct 2018`).

The `==` doubled pair in the centre zone is a LocoScript 2 page number placeholder — at print time LocoScript would have expanded it to the actual page number. The surrounding control bytes (`22 61 44`, `13 04 50` etc.) are part of the page number token machinery. Since page numbers cannot be resolved statically, the entire page number zone is silently discarded; only the document reference text is extracted as `doc.footer`. A future enhancement could render the page number zone as a `[PAGE]` placeholder.

## Untested document types
The parser was developed and validated against a single sample document (a research notes file). Locoscript 2 supported different document types (letters, labels, etc.) which may use different page-layout structures or section-break patterns not yet seen. New files may surface unrecognised `22 61 0b` variants or other control sequences — see the debugging workflow in `CLAUDE.md`.

## JOY format files
233 files in the sample set use the `JOY` magic word rather than `DOC`. These have a different binary structure — no `22 61 0b` paragraph anchor, different word separator and paragraph break bytes — and require a separate parser. Attempting to convert a JOY file currently raises an informative `ParseError` and logs the failure. Two sub-versions exist: `01 04` and `01 02`, with different word separators and paragraph structures.

---

# Shadow Copy Mode

## Overview
An optional mode in the application that mirrors an entire folder structure, producing converted versions of all Locoscript 2 files found within it.

## Requirements

- The application shall provide a "Create processed shadow copy" option in the UI
- The user selects a source folder (rather than individual files)
- The application traverses the full folder structure recursively, locating all Locoscript 2 files (identified by their `DOC` magic bytes, regardless of file extension)
- A mirror folder structure is created at the same level as the source folder, with the top-level folder named by prepending "Converted_" to the source folder name (e.g. source folder "Archive" → output folder "Converted_Archive")
- The subfolder hierarchy within the mirror structure matches the source exactly
- Each located Locoscript 2 file is converted and saved into the corresponding location in the mirror structure, using the selected output format and the same filename with the new extension added
- The user selects the output format (TXT, RTF, DOCX) as with normal conversion
- If the top-level mirror folder already exists, the user is prompted to confirm before proceeding
- Error handling follows the same rules as batch conversion: failures are logged to DocConvertor-Error.log in the corresponding mirror subfolder, processing continues, and a summary is shown on completion
- The completion summary should include the time taken, count of files converted, and count of failures

---

# Locoscript 2 Binary Format Reference

This section documents the binary encoding patterns discovered through reverse-engineering of real Locoscript 2 document files (Amstrad PCW word processor format, circa late 1980s–early 1990s). All byte values are hexadecimal.

## File Header

Every valid Locoscript 2 file begins with a three-byte ASCII magic number. Two magic values have been identified:

| Magic | Hex | Status |
|-------|-----|--------|
| `DOC` | `44 4f 43` | Supported — full parser implemented |
| `JOY` | `4a 4f 59` | Not currently supported — see Known Limitations |

For `DOC` files, content parsing begins at the first occurrence of the paragraph content marker `22 XX 0b` — everything before it is a document header containing page layout and section metadata that is not needed for text extraction.

### Layout Table (`0x2C6`)

The layout table at `0x2C6` contains 10 × 73-byte entries describing page layout configurations. Key fields in each entry:

| Entry offset | Field | Notes |
|---|---|---|
| +11 | Scale pitch byte `P` | `0x18` = 10cpi; `0x14` = 12cpi |
| +13 | Point size × 10 | `0x78` = 12pt |
| +33..+47 | 15 tab stop positions | Absolute positions in scale pitch units; `0x00` = unused |

**Scale pitch unit conversion:**
```
twips_per_unit = P × 6
```
For `P = 0x18` (10cpi): `twips_per_unit = 144` (= 0.1 inch × 1440 twips/inch ✓)

Tab stop values read from +33..+47 are absolute positions from the left margin. A value of `0x18` (24) at 10cpi = 24 × 0.1" = 2.4" (the LocoScript default tab stop spacing). Custom values have been confirmed in real files (e.g. `Memorial.002` uses `0x27`, `0x2c`, `0x31`).

`JOY` files use a different binary structure (no `22 61 0b` anchor, different word separator and paragraph break bytes) and require a separate parser. Attempting to parse a JOY file raises a `ParseError` with an informative message.

## Byte Encoding

Body text is stored as raw bytes in the range `0x20–0x7E` (printable ASCII). Characters outside this range are control codes, structural metadata, or extended character mappings. Known extended character mappings are listed below. Unmappable bytes are substituted with `?`.

| Byte | Unicode | Character | Evidence |
|------|---------|-----------|----------|
| `84` | U+2019  | `'` (right single quote) | "Kelly's" |
| `8F` | U+00E6  | `æ` | "Archæology", "orthopaedic" |
| `B4` | U+00E9  | `é` | "Café", "née" |
| `C3` | U+00E8  | `è` | "dix-huitième", "Adèle" |
| `E4` | U+00EA  | `ê` | "Fête" |
| `E8` | U+00F4  | `ô` | "Dépôt" |
| `E9` | U+00A3  | `£` | confirmed; diverges from Amstrad CP/M Plus table (which maps `E9` → û) |
| `FA` | U+00E7  | `ç` | "façade" (second encoding alongside ENQ 5-byte sequence) |

All mappings are built empirically from real LocoScript 2 file evidence. The Amstrad CP/M Plus character table (Wikipedia) is **not** the LocoScript 2 encoding and must not be applied wholesale. Bytes in the range `0x80–0xFF` that are not in this table are substituted with `?`.

Extended characters that require more than one byte are encoded using the ENQ sequence described below.

## Control Codes and Sequences

### Word Separator — `02`
A single byte `02` represents an inter-word space. Words within a run are separated by this rather than a literal `0x20` space byte.

### Paragraph Break — `13 04 50`
Three-byte sequence marking the end of a paragraph. May be followed by optional trailing indent metadata (see below). Starts a new paragraph in the output.

### Italic On — `13 04 64`
Three-byte sequence that begins an italic text run. Italic state is tracked and applied to subsequent `TextRun` objects until italic is turned off.

### Line Break / Italic Off — `13 04 78`
Three-byte sequence. If italic is currently active it acts as "italic off" (end of italic run). If italic is not active it emits a hard line break (`\n`) within the current paragraph.

### Tab / Citation Indent — `09 05 01` + 2 param bytes
Five bytes total. Emits a tab character (`\t`) in the output. The first param byte (`XX`) encodes the **explicit tab column position** in scale pitch units (`XX × twips_per_unit` gives the RTF `\tx` position). A zero value means no explicit position. The second param byte is always the same value (doubled-pair pattern) and is consumed along with the first.

### Paragraph Indent Marker — `08 05 01` + 2 param bytes
Five bytes total. Structural paragraph indent/style marker. Emits nothing. The doubled-pair value XX (where data[i+3] == data[i+4]) encodes one of two things:

| XX range | Meaning | Action |
|----------|---------|--------|
| `0x01`–`0x1F` | Left indent in scale pitch units | Set `para.left_indent = XX × twips_per_unit` |
| `0x20`+ | Bibliography/reference paragraph style code | Consume silently — these are style identifiers, not indent amounts |
| `0x00` | No indent | Consume silently |

Every XX ≥ `0x20` occurrence across real sample files (HENCOTES, BUILDNGS, BINDINDX.HEX) is followed by a book or reference title, confirming the style-code interpretation. Without this handler the two trailing param bytes (which are often printable) leak into the output as doubled-pair artefacts.

### ENQ Extended Character — `05 base 01 diacritic 01`
A five-byte sequence encoding an accented or extended character:

```
05  base_char  01  diacritic_code  01
```

- `base_char` is the ASCII base letter (`0x21`–`0x7E`).
- `diacritic_code` is a small control byte identifying the accent type.
- The sequence may be followed by an optional structural doubled-pair indent marker (`01 XX XX` where `XX == XX` and `XX >= 0x20`); these three bytes are consumed and not output.

Known `(base_char, diacritic_code)` → character mappings confirmed in real sample files:

| Base | Diacritic | Unicode | Character |
|------|-----------|---------|-----------|
| `63` ('c') | `13` | U+00E7 | `ç` (e.g. "façade", "Français") |

For unrecognised combinations the base character is emitted as a best-effort fallback.

### Inline Formatting — `08 XX` (on) / `09 XX` (off)
Two-byte sequences that toggle inline character formatting. The second byte identifies the format type:

| Second byte | Format |
|-------------|--------|
| `00` | Bold |
| `02` | Underline |
| `06` | Superscript |
| `07` | Subscript |

`08 05` and `09 05` are not formatting toggles — they are handled separately as paragraph indent and tab markers respectively.

After the two-byte sequence, any non-printable parameter bytes are consumed (excluding `02` word separators, `06` hyphen/space, and `13` formatting prefixes). Bold-on (`08 00`) and superscript-off (`09 06`) are followed by `01 XX XX` where `XX XX` is a doubled-pair indent marker; these are also consumed.

### Paragraph Alignment — `11 06` (centre) / `10 07` or `10 04` (right)

Two-byte sequences setting the alignment of the current paragraph:

| Sequence | Alignment |
|----------|-----------|
| `11 06` (DC1 + ACK) | Centre |
| `10 07` (DLE + BEL) | Right |
| `10 04` (DLE + EOT) | Right |

Both bytes are consumed as a unit; the second byte is a parameter and does not produce output. Alignment defaults to left when no alignment code is present. Confirmed from real sample files — `11 06` appears immediately after `22 61 0b` paragraph content blocks in ~4,000 occurrences across the sample set.

RTF output uses `\qc` (centre) or `\qr` (right) on the `\pard` control word. DOCX output sets `paragraph.alignment` to `WD_ALIGN_PARAGRAPH.CENTER` or `WD_ALIGN_PARAGRAPH.RIGHT`.

### Contents Page Separators — `0f 01` / `0f 02` (non-`22 61` files only)

In `22 6d` and `1e 74` variant files, paragraph separators use `0f 01` and `0f 02` immediately preceding a `PP ctrl 0b` paragraph block, rather than `13 04 50`:

| Pattern | Meaning |
|---------|---------|
| `0f 02 PP ctrl 0b [...]` | Paragraph boundary — flush current paragraph, start new one |
| `0f 01 PP ctrl 0b [...]` | Line break within paragraph |

These handlers only fire when `ctrl_byte != 0x61` (i.e., non-standard variants). In standard `22 61` files the same byte patterns have different semantics and are handled by existing logic.

Each Contents Page entry is followed by a `0f 04 27 6d 01 XX XX` left-indent tab stop (the `27 6d` bytes encode the column position and ctrl_byte delimiter). The `22 ctrl 0b` block immediately after `0f 01`/`0f 02` may have B6=`0f` B7=`04` or B7=`0f` in its tail — both are left for the main loop's `0f 04` handler by using a shortened skip (6 or 7 bytes respectively).

### SI Tab / Hanging Indent — `0f 04` (tab) / `0f 05` (hanging indent)
Two-byte prefix followed by optional parameter bytes:

```
0f [04|05]
[optional non-printable param bytes]
B1  B2   ← two printable bytes (B1 = column position, B2 = body ctrl_byte)
[optional: 01 separator + identical-byte indent pair]
→ content
```

`0f 04` emits a tab character (`\t`). `0f 05` is a hanging-indent marker that emits nothing. In both cases all parameter and indent bytes are consumed.

**B1** encodes the intended tab/indent column in scale pitch units (same unit as the `09 05 01` param byte). **B2** is always equal to the body ctrl_byte of the file (`0x61`, `0x6d`, or `0x42`) and acts as a structural delimiter. The parser records `B1 × twips_per_unit` as an explicit tab stop on the paragraph for RTF/DOCX rendering.

### Indent Metadata — `09 00 01` [+ doubled printable pair]
Note: `09 00` is now recognised as bold-off (see Inline Formatting above). The trailing `01 XX XX` params are consumed as part of the bold-off handler. This entry is retained for historical reference only.

### Section / Page Break — `0e 01` or `0e 02`
A two-byte sequence where `0e` is followed by `01` (section break) or `02` (page break). This is followed by a variable-length binary metadata block encoding the new section's page layout. The entire block is skipped by jumping forward to the next `22 61 0b` paragraph content marker.

Whether the break creates a paragraph boundary depends on what precedes the `0e` byte (body section only):

| Byte before `0e` | Meaning | Action |
|-----------------|---------|--------|
| `0x02` (word separator) or printable (`0x20`–`0x7e`) | Break is mid-sentence — layout/column switch only | Skip layout block; **do not flush paragraph** |
| Any other byte (e.g. follows `13 04 78` line break) | Break follows a genuine paragraph end | Flush paragraph, then skip layout block |

This distinction only applies within the body (`i >= body_start`). Section breaks in the pre-body zone (between header, footer, and body sections) always flush the paragraph unconditionally.

When the break is a genuine paragraph boundary (not mid-sentence), the following paragraph has `page_break_before = True`. Converters emit this as:

| Format | Output |
|--------|--------|
| TXT | `--- page break ---` separator before the paragraph |
| RTF | `\page` control word prepended to the paragraph's `\pard` line |
| DOCX | `<w:pageBreakBefore/>` in `<w:pPr>` (paragraph property, not an inline run break) |

### Hyphen / Extra Space — `06`
Contextual byte with three behaviours:

| Context | Output | Example |
|---------|--------|---------|
| Both neighbours are `02` word separators (`02 06 02`) | `-` (dash separator) | "Henhouse - domestic hens", "6.3.2015 - 100 Years Ago" |
| Between two printable chars | `-` (hyphen) | "go-ahead", "vice-chairman", "627-640" |
| Adjacent to a word separator (one side only), another `06`, or a non-printable preceding byte | ` ` (space) | spacing/layout use |

## Control Sequence Prefix — `22 61` / `22 6d` / `22 42` / `1e 74`

Body paragraphs are anchored by a three-byte marker `PP XX 0b`, where `PP` is the prefix byte and `XX` is the ctrl_byte. Four variants have been confirmed:

| `PP` | `XX` | Files | Notes |
|------|------|-------|-------|
| `0x22` | `0x61` (`"a`) | Standard DOC files | Most common |
| `0x22` | `0x6d` (`"m`) | `BUILDNGS.A-C`, `MARKETPL.*` | Second variant |
| `0x22` | `0x42` (`"B`) | `Memorial.002` | Third variant — body only; header zone uses `0x61` |
| `0x1e` | `0x74` | `BINDINDX.HEX` and similar index files | Fourth variant — RS prefix byte instead of `"` |

The parser detects the correct variant using `_detect_variant(data) -> (prefix_byte, ctrl_byte)`, which counts all `PP XX 0b` occurrences for `PP` in `{0x22, 0x1e}` and returns the pair with the highest combined count. This correctly handles files like `Memorial.002` where the header/transition zone contains a handful of `22 61 0b` blocks before the `22 42 0b` body content begins.

When `PP XX` is followed by a word separator (`02`) or `06`, the sequence is treated as literal text rather than a control code (only applies to `PP = 0x22`; `0x1e` files never embed `1e XX` as literal text).

### `1e 74` Variant — additional details

The `0x1e` prefix variant uses RS (ASCII Record Separator) instead of `"` (double-quote). Key behavioural differences from `0x22` variants:

- **Doubled-pair threshold:** all indent values in `1e 74` files fall in `0x00–0x1f`, so the universal `> 0` threshold (see Trailing Indent Metadata Pattern) applies.
- **Self-referential sequence:** `1e 1e 74 01 00 00 00 23` (analogous to `22 61 61`) — always binary layout metadata, never body text. The parser skips directly to the next `1e 74 0b` block.
- **`22 6d 6d` embedded in body blobs:** the pre-body zone's `22 6d` self-referential sequence (`22 6d 6d`) can appear inside `1e 74` body binary blobs. Detected using `prebody_ctrl_byte` (the ctrl byte discovered by running `_detect_variant` on the pre-body slice); when seen, the parser skips to the next `1e 74 0b` block, preventing `"mmxd`-style text artefacts.
- **`0f 00 1e 74 0b` (section boundary):** always preceded by the self-referential sequence. After the sequence skip lands on `1e 74 0b`, this is treated silently (no paragraph flush).
- **Page-break binary blobs:** `1e 74 0b` blocks that signal a page break are identified by a `07 03` marker at one of three positions within the block header. Three forms confirmed in BINDINDX.HEX:
  - `1e 74 0b B3 B4 07 03 …` — `07 03` at B5/B6 (standard MEMORIAL-style, already handled)
  - `1e 74 0b cc 10 14 90 00 07 03 …` — B5=`0x14` (font-size bytes) shifts marker to B8/B9
  - `1e 74 0b ae 10 02 07 03 00 …` — extra param byte shifts marker to B6/B7
  In all cases the parser calls `flush_run(); flush_para(); current_para.page_break_before = True` before jumping to the next `1e 74 0b`. The `B5=0x07` check is guarded in `22`-prefix files: blocks with B3 ≥ `0x80` and B4 = `0x0e` are structural section headers that legitimately carry `07 03` as binary layout data — these are handled by `_skip_ctrl_sequence` and must not trigger a page break.
  
  **`flush_para` propagation:** when `flush_para()` discards an empty paragraph (no content runs), it propagates `page_break_before` to the replacement paragraph. This ensures the flag survives intermediate `0f 02` section-separator flushes (which may occur between a `07 03` block and the first content paragraph — e.g. the "Contents" heading in BINDINDX.HEX).
- **Per-page LocoScript control labels:** some `1e 74` body blocks accumulate text such as `"Last page Header / Footer disabled?"` before encountering a `07 03` page-break marker. These are per-page LocoScript UI metadata labels, not document content. When `07 03` is seen in the main parse loop (for `1e`-prefix files), any accumulated text is discarded, `flush_para()` is called, `page_break_before` is set on the next paragraph, and the parser jumps to the next `1e 74 0b`.
- **Scale pitch:** `0x14` (12cpi) in `BINDINDX.HEX`, giving `twips_per_unit = 120`.
- **B5/B6 font-size encoding:** when B5=`0x14`, B6 encodes the font size in tenths of a point (`0x78` = 12pt, `0x90` = 14.4pt). The parser sets `para.font_size = B6 / 10.0` on the current paragraph. RTF output adds `\fs{int(font_size×2)}` before run content; DOCX sets `run.font.size = Pt(font_size)`.
- **B4 sub-entry indent:** B4 ≤ `0x0c` marks a *candidate* sub-entry. The 576-twip (0.4") indent is applied only when **no trailing `01 XX XX` doubled pair follows the block** — the presence of a trailing pair identifies a top-level entry even when B4 ≤ `0x0c`. Genuine indented cross-references (e.g. `see Cockshaw`) have B4 ≤ `0x0c` and no trailing pair; top-level entries (e.g. `Bell, Henry & Sons`) have B4 ≤ `0x0c` but carry a large trailing pair (values `0x19`–`0x2b`). B4 ≥ `0x0d` is always top-level (unindented).

### Control Type `0b` — Paragraph Content Block
This is the most important control type. It marks the start of a new paragraph's content area and is used as a navigation anchor throughout the parser. The full structure is 8 bytes:

```
22 XX 0b | B3 B4 B5 | B6 B7
          3 param    2 indent
```

If B5=`13` and B6=`04` (a `13 04` formatting prefix embedded in the param bytes), the skip is shortened to 5 bytes, leaving `13 04 XX` for the main loop to handle as italic-on (`64`), italic-off/line-break (`78`), or paragraph break (`50`).

Several structural variants exist:

| Condition | Meaning | Action |
|---|---|---|
| `B6 B7` = `13 04` | Formatting prefix immediately follows — leave for main loop | Skip 6 bytes |
| `B6..B8` = `78 00 01` or `78 00 0a`, and `B9 == B10 >= 0x20` | Extended indent variant; followed by a doubled printable pair. `0a` separator confirmed in `22 6d` files. | Skip 11 bytes |
| `B3 >= 0x80` and `B4` = `0e` (**22-prefix files only**) | Structural section/layout header block; never contains body text (e.g. `c4 0e` in standard files, `a6 0e` / `88 0e` / `84 0e` in `22 6d` variant files; low-B3 values such as `3a 0e` are normal content blocks). **Does not apply to `1e` files** — in `1e 74` variant files `B4 = 0x0e` is simply a top-level entry marker (B4 > 0x0c), not a structural indicator. | Skip to next `22 XX 0b` |
| `B3 < 0x80`, `B6 B7` = `78 00`, no valid doubled pair, and `ctrl_byte ≠ 0x61` | Section-start marker in `22 6d`/`22 42` variant files. Carries variable-length structural trailing bytes (separator bytes, column positions, etc.) containing printable values that must not be emitted. Standard `22 61` files never use this trailing structure. | Skip 8 bytes, then scan forward to next `11` alignment marker or `22 XX` control prefix |
| `B4 B5 B6` = `0a 09 00` | Tab-indent variant; followed by `01` + doubled printable pair | Skip 11 bytes |
| `B5` = `0f` and `B6` = `0x04` | SI tab indicator embedded in paragraph header; structure is `B3 B4 0f 04 B1 B2 [01 PP PP]` where B1 = column position and B2 = ctrl_byte (e.g. `88 02 0f 04 3b 61 01 0b 0b` in MEMORIAL.002 column lists) | Skip 9 bytes then consume optional `01` separator + identical-byte indent pair |
| `B6` = `0f` and `B7` = `0x04` | Column spec shifted one byte later by a B5 sequence number (values `0x31`/`0x32`/`0x33` seen in `BINDINDX.HEX` sub-entries, e.g. `1e 74 0b 8e 0d 31 0f 04 23 74 01 0d 0d`). Structure: `B3 B4 B5 0f 04 B1 B2 [01 PP PP]`. No tab emitted. | Skip 10 bytes then consume optional `01` separator + identical-byte indent pair |
| `B7 B8` = `13 04` | Formatting prefix one byte later — leave for main loop | Skip 7 bytes |
| `B7 B8` = `22 XX` | Nested control prefix at indent position — leave for main loop | Skip 7 bytes |
| (default) | Standard 8-byte block | Skip 8 bytes |

**MEMORIAL-style paragraph breaks (body only):** In some documents (e.g. `MEMORIAL.002`) paragraphs are delimited by `22 XX 0b` block pairs rather than `13 04 50`. The distinctive signature is `B3 = 0xe8` and `B4 = 0x05` — when this appears in the body the parser flushes the current paragraph. A page-break variant adds `B5 = 0x07`, which also triggers a jump past the binary layout block that follows.

### Other Control Types
All other control types (`0c`, `0d`, `36`, etc.) follow a variable-length structure: skip the 2-byte prefix + type byte + 1 extra parameter byte (4 bytes total), then consume any additional non-printable parameter bytes (excluding `02` word separators and `13` which may begin a formatting sequence), then skip any doubled-pair indent markers.

**Self-referential sequences — `22 XX XX` (type == ctrl_byte):** When the control type byte equals the ctrl_byte itself (e.g. `22 61 61` in standard files, `22 6d 6d` in `22 6d` variant files), the sequence is always binary layout/page metadata and never contains body text. The parser skips directly to the next `22 XX 0b` paragraph content block rather than using the variable-length skip, which would otherwise stop at the first printable byte and leak binary data as text artefacts.

## Trailing Indent Metadata Pattern

After many control sequences a 4-byte metadata suffix appears:

```
00 01 XX XX    (where XX == XX and XX > 0)
```

The two identical bytes are a doubled-pair indent marker encoding the paragraph's left margin. This suffix is consumed after: `13 04 50` (paragraph break), `13 04 64` (italic on), `13 04 78` (line break/italic off), and after any `22 61` control sequence skip.

The threshold is `XX > 0` (not `XX >= 0x20`). Values below `0x20` (e.g. `0x0e = 14`) are valid indent amounts in all file variants and must be consumed to prevent the following bytes from being misinterpreted as control codes. The original `>= 0x20` threshold caused `00 01 0e 0e 0e 02` to leave `0e 02` visible to the section-break handler (confirmed in BUILDNGS.H). Using `> 0` also correctly consumes low-value pairs in `1e 74` variant files (e.g. `00 01 06 06`), avoiding spurious content artifacts.

## Doubled-Pair Indent Markers

Throughout the format, indent and margin values are encoded as a pair of identical printable bytes (e.g. `4a 4a` = 'JJ', `47 47` = 'GG', `3d 3d` = '==', `54 54` = 'TT'). These are structural metadata, never text content. They appear at the tail of paragraph content blocks and after various trailing metadata sequences.

## Document Structure (Typical)

```
[DOC header — page layout, section metadata]
22 61 0b ...   ← first paragraph content block (content start anchor)
[text bytes, 02 separators, 13 04 xx formatting codes]
13 04 50 ...   ← paragraph break
22 61 0b ...   ← next paragraph content block
...
0e 01 / 0e 02  ← section/page break + binary layout block
22 61 0b ...   ← paragraph content resumes after section break
...
```
