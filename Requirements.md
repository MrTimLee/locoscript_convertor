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
Implemented. Headers and footers are now extracted as separate `Paragraph` objects (`doc.header`, `doc.footer`) and rendered appropriately in all three output formats: TXT uses `---` separators, RTF uses `\header`/`\footer` groups, DOCX populates `section.header`/`section.footer`. Confirmed working on HENCOTES (header + footer), BUILDNGS.H (footer only), and BREWERS.5 (header + footer in a `22 6d` variant file).

### `22 6d` body_start detection (low-B3 footer blocks)
In `22 6d` variant files, the footer block can have a **low B3 byte** (e.g. `B3=0x13` in BREWERS.5), unlike the high-B3 structural header blocks (`a6 0e`) that bracket it. The fallback scan in `_find_body_start` previously misidentified this low-B3 footer block as the body start, causing footer content to appear as body text and the real header/footer to be lost.

Fix: when the fallback scan considers a low-B3 candidate (either because a high-B3 block has been seen, or because `B5 ≠ 0x14`), it now checks for a `00 00` NUL terminator between the candidate and the next `22 ctrl 0b` block. Pre-body header/footer zones always end with two NUL bytes before the binary layout blob; body paragraphs never have `00 00` between them. If NUL is found, the block is skipped; otherwise it is accepted as body_start. Confirmed: BREWERS.5 body_start correctly resolves to 0x6FD (the "Contents" heading paragraph).

**Refinement (MEMORIAL.002):** The NUL search is now restricted to bytes that appear **after the first printable byte** in the scan range. In some documents (e.g. MEMORIAL.002 `22 61` letter format), the block header is followed by binary parameter bytes that contain `00 00` before any printable text. Without this refinement, the false positive NUL detection caused body_start to advance too far (to 0x834 rather than the correct 0x76d). The rule is: if no printable byte exists before `00 00`, the NUL is binary metadata and does not disqualify the block; only a `00 00` that follows text is a genuine pre-body terminator.

### Page number zone in footers
Footer sections in Locoscript 2 use a two-zone layout: a **centre-aligned page number zone** followed by a **right-aligned document reference zone**. The page number zone is identified by a `11 06` (centre alignment) code followed by a page-number token sequence. The document reference zone begins after a `10 07` (right alignment) code and contains the human-authored text (e.g. `CND 4.1,  4 Oct 2018`).

The page number token is `07 06` (BEL + ACK), confirmed across HENCOTES and BREWERS.5. It is followed by a SOH-counted display field: `01 N N [N bytes]`, where the N display bytes are the on-screen placeholder LocoScript rendered (e.g. `3d 3d 02 06` = `==` + word-sep + space). The parser emits a `page_number=True` `TextRun` for the token and consumes the display bytes; converters render this as `\chpgn` (RTF), a `PAGE` field (DOCX), or `[PAGE]` (TXT).

### Footer two-zone tab layout
Implemented. The `10 07` (right alignment) code in footer context sets `Paragraph.footer_tab = True` instead of `alignment = 'right'`. Converters render the footer as a two-zone tab-stop layout: a leading tab moves to the centre tab stop (page number zone, rendered with `\chpgn` / PAGE field / `[PAGE]`), then a second tab moves to the right tab stop (document reference zone). Tab positions are hardcoded for A4 with 1-inch margins: centre tab at 4513 twips, right tab at 9026 twips (printable width = 9026 twips).

#### Page margin bytes (known limitation)
LocoScript 2 files contain page margin bytes at offset `0x2BA`/`0x2BC` in the file header. Their unit system has not been confirmed (values differ between files: HENCOTES=`0x28`, BREWERS.5=`0x30`). The Java reference converter also hardcodes A4 1-inch margins for all files. Until the margin byte encoding is understood, the tab positions above use the hardcoded A4 values. See `Page-Margin-Investigation.md` (local only).

### Per-page LocoScript control labels in `22 6d` body
BREWERS.5 contains a per-page LocoScript UI label "Last page: Header and Footer disabled." as body text (para[231]). This label appears directly before a page break marker (`a6 0e 07 03`) and is structurally indistinguishable from a regular paragraph that precedes a page break — after `0f 02` flushes the preceding content, `current_para` is identically fresh whether the prior text was a label or real content. No reliable binary signal distinguishes the two at parse time. The label is therefore emitted as body text. This is a cosmetic artefact only (one paragraph out of 232 in BREWERS.5). Label suppression is deferred as a known limitation.

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

### Font Table (`0x0138`)

The font table at `0x0138` contains 10 × 28-byte entries listing the fonts installed in the document:

| Entry offset | Field | Notes |
|---|---|---|
| +0 | Name length byte | 0 = unused slot |
| +1..+23 | Font name (Latin-1) | Up to 23 characters |
| +24..+27 | Trailing data | Internal reference bytes; encoding not decoded |

Slot 0 is the document default face. Slot 2 is the alternate face used for inscription/serif sections (see Format B below). The parser reads all 10 slot names into `Document.fonts`.

Known font names confirmed in real files: "CG Times", "Sans H" (= CG Times on a different printer config), "Roman T", "LX Roman", "LX Sanserif", "CourierCondensed", "LX Bodoni Poster", "LX Broadway", "LX Brush", "LX Park Avenue", "LX Prestige". RTF output uses `\froman`/`\fswiss`/`\fmodern` family tags derived from the name.

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

### Font Face Switch — Format B (`22 61 TYPE 0a 0d`)

A sub-sequence within a body paragraph that switches the active font face from the document default (slot 0) to the alternate face (slot 2).  Identified by three characteristics:

- Starts with `22 61 TYPE` where TYPE is any byte **other than** `0x0b` (paragraph anchor) or the file's ctrl_byte (self-referential)
- Followed immediately by `0a 0d` (LF control byte with parameter x=13; x=9 for normal paragraphs per the reference doc — x=13 distinguishes a style change)
- Appears only in body paragraphs of documents that have a non-empty font slot 2

Confirmed in four files: MEMORIAL.002 (Roman T, slot 2), ABBEYGRD.4, MEMORIAL.004, DUNWOODY (all LX Roman, slot 2). Zero occurrences in single-font files (HENCOTES, BREWERS.5, BUILDNGS.*).

The TYPE byte (values 0x22–0x38 observed) is a screen-column position hint, identical in role to the TYPE byte in Format A (`22 61 TYPE 01 YY YY`). It does NOT encode a font slot index.

After `0a 0d`, the byte stream continues normally: optional `02` word separator, optional `13 04 XX` font-size commands, optional `01 ZZ ZZ` SOH indent hint, then body text. The face switch applies to all runs in the current paragraph and resets at the next paragraph boundary (`flush_para()`). No explicit "switch back" command has been found.

RTF output wraps the run in `{\f1 ...}` (scoped group) referencing the `\f1` font table entry (slot 2). DOCX sets `run.font.name = font_face`. Documents with no slot-2 font silently ignore Format B.

### Font Size — `13 04 xx`
Three-byte inline font-size command. The third byte encodes the point size × 10:

| Byte | Value | Point size |
|------|-------|-----------|
| `50` | 80    | 8 pt       |
| `64` | 100   | 10 pt      |
| `78` | 120   | 12 pt      |
| `8c` | 140   | 14 pt      |

The command is purely inline — it carries no structural meaning and does not break paragraphs. The new font size applies to subsequent `TextRun` objects within the current paragraph. May be followed by optional trailing metadata (see below).

RTF output wraps the affected run in an RTF group `{\fsN ...}` so the size change is scoped to that run only. DOCX output sets `run.font.size = Pt(size)` on each affected run.

### Paragraph Break / Line Break — `0f 02` / `0f 01` + `PP ctrl 0b` block
`0f` (SI, Shift In) followed by a sub-type byte and a `PP ctrl 0b` block anchor marks paragraph and line boundaries in all file variants:

| Pattern | Meaning |
|---------|---------|
| `0f 02 PP ctrl 0b [...]` | Paragraph boundary — flush current paragraph, start new one |
| `0f 01 PP ctrl 0b [...]` | Soft return within paragraph — emit `\n`, same paragraph continues in next block |

The check `data[i+2] == prefix_byte and data[i+3] == ctrl_byte` guards against false positives inside binary block headers. `0f` bytes not followed by `01`/`02` + a valid block anchor (e.g. `0f 00`, `0f 0f`) fall through to non-printable handling and are ignored.

### Italic Off — `09 05 01` + 2 byte-count hint bytes
Five bytes total. Turns italic off (consistent with the `09 XX` off pattern, second byte `0x05` = italic). The two trailing bytes YY YY are a byte-count layout hint encoding the length of the following non-italic text segment (same convention as the italic-on form — see below). Consumed silently. No tab character is emitted.

### Italic On — `08 05 01` + 2 byte-count hint bytes
Five bytes total. Turns italic on (consistent with the `08 XX` on pattern, second byte `0x05` = italic). The two trailing bytes `XX XX` are a **LocoScript screen-layout hint** encoding the byte count of the following italic text segment (e.g. `XX = 0x0a` for "Hex. Cour." which is 10 bytes, `XX = 0x11` for "Kelly's Directory" which is 17 bytes). They carry no indent semantics and are consumed silently in all cases. Without this handler the two trailing bytes (which are often printable) leak into the output as doubled-pair artefacts.

The pairing rule `09 05 01 YY YY` (italic off) works identically — YY is the byte count of the following non-italic text segment. Both confirmed exhaustively against HENCOTES (see `Indent Investigation.md`).

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
| `05` | Italic |
| `06` | Superscript |
| `07` | Subscript |

Bare `08 05` / `09 05` (not followed by `01`) use this table. The 5-byte `08 05 01 XX XX` and `09 05 01 XX XX` forms are handled separately — see *Italic On* and *Italic Off* below — and carry a byte-count layout hint in the two trailing bytes.

After the two-byte sequence, any non-printable parameter bytes are consumed (excluding `02` word separators, `06` hyphen/space, and `13` formatting prefixes). Bold-on (`08 00`) and superscript-off (`09 06`) are followed by `01 XX XX` where `XX XX` is a doubled-pair indent marker; these are also consumed.

### Page Number Token — `07 06`

BEL (`0x07`) followed by ACK (`0x06`) is the LocoScript 2 current-page-number token. Confirmed in the footer zones of HENCOTES and BREWERS.5 (the only two files in the sample set with page numbers in their footers).

The token is followed by a SOH-counted display field:

```
07 06  01 N N  [N bytes]
```

- `07 06` — page number token
- `01 N N` — SOH byte + count byte N repeated twice
- `[N bytes]` — the display content LocoScript rendered on screen (e.g. `3d 3d 02 06` = `==` + word-sep + space, where `==` was the visual placeholder for the page number)

The parser emits a `page_number=True` `TextRun` (with no literal text) and consumes the display bytes. Converters render this as `\chpgn` (RTF), a `PAGE` field (DOCX), or `[PAGE]` (TXT).

### Paragraph Alignment — `11 06` (centre) / `10 07` or `10 04` (right)

Two-byte sequences setting the alignment of the current paragraph:

| Sequence | Alignment |
|----------|-----------|
| `11 06` (DC1 + ACK) | Centre |
| `10 07` (DLE + BEL) | Right |
| `10 04` (DLE + EOT) | Right |

Both bytes are consumed as a unit; the second byte is a parameter and does not produce output. Alignment defaults to left when no alignment code is present. Confirmed from real sample files — `11 06` appears immediately after `22 61 0b` paragraph content blocks in ~4,000 occurrences across the sample set.

**Context-sensitive `10 07`/`10 04` behaviour:** when the code appears at the **start** of a paragraph (no content accumulated yet) and in a non-footer section, it sets `alignment='right'` for the whole paragraph (standard whole-paragraph right alignment). When it appears **mid-paragraph** (content has already been accumulated) and in a non-footer section, it splits the paragraph into a left zone and a right zone on the same line — identical to the footer two-zone tab layout. The parser sets `Paragraph.inline_right_tab = True`, emits a `\t` tab character into the current text, and subsequent text forms the right-aligned zone. Converters apply a right tab stop at the right margin (9026 twips, hardcoded A4 1-inch margins), identical to the footer tab behaviour.

RTF output uses `\qc` (centre) or `\qr` (right) on the `\pard` control word. DOCX output sets `paragraph.alignment` to `WD_ALIGN_PARAGRAPH.CENTER` or `WD_ALIGN_PARAGRAPH.RIGHT`. For `inline_right_tab` paragraphs, RTF uses `\tqr\tx9026` and DOCX adds a right tab stop XML element.

### SI Tab / Hanging Indent preamble

Each Contents Page entry (in `22 6d` and `1e 74` variant files) is followed by a `0f 04 27 6d 01 XX XX` left-indent tab stop (the `27 6d` bytes encode the column position and ctrl_byte delimiter). The `22 ctrl 0b` block immediately after `0f 01`/`0f 02` may have B6=`0f` B7=`04` or B7=`0f` in its tail — both are left for the main loop's `0f 04` handler by using a shortened skip (6 or 7 bytes respectively).

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
| Any other byte (e.g. follows `0f 02` paragraph break or `13 04 xx` font-size change) | Break follows a genuine paragraph end | Flush paragraph, then skip layout block |

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

If B5=`13` and B6=`04` (a `13 04` font-size prefix embedded in the param bytes), the skip is shortened to 5 bytes, leaving `13 04 XX` for the main loop to handle as an inline font-size change.

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
| `B5` = `0x11` and `B6` = `0x06` | Centre-alignment marker embedded in block header. Skip 5 bytes (up to B4) and leave `11 06` for the main loop's alignment handler. Confirmed in `1e`-prefix (BINDINDX) and `22`-prefix files (HENCOTES section headings, MEMORIAL.002 body sections). | Skip 5 bytes |
| `B7 B8` = `13 04` | Formatting prefix one byte later — leave for main loop | Skip 7 bytes |
| `B7 B8` = `22 XX` | Nested control prefix at indent position — leave for main loop | Skip 7 bytes |
| `B5` = `0x10` and `B6` = `0x04` | Right-tab zone header (MEMORIAL.002 form): `22 XX 0b B3 B4 10 04 22 3d XX`. Default 8-byte skip lands at `3d XX` ('='), emitting '=' artefacts. Skip 10 bytes to clear the entire sequence. Confirmed across 15 occurrences in MEMORIAL.002. | Skip 10 bytes |
| `B5` = `0x14`, `B6` = `0x78`, `B7` = `0x00`, `B8` = `0x10`, `B9` = `0x04` | Compound PASSCHENDAELE variant: font-size bytes (`14 78 00`) immediately before right-tab zone code (`10 04`). Example: `22 61 0b f8 01 14 78 00 10 04 22 3d 3d`. Default skip lands in the middle, causing `"==` artefacts. Skip 10 bytes, then consume the following prefix byte (`22`) and doubled pair (`3d 3d`). | Skip 10 bytes + optional prefix + optional doubled pair |
| (default) | Standard 8-byte block | Skip 8 bytes |

**MEMORIAL-style paragraph breaks / section separators (body only):** In some documents (e.g. `MEMORIAL.002`) paragraphs are delimited by `22 XX 0b` block pairs rather than `0f 02 PP ctrl 0b`. The distinctive signature is `B3 = 0xe8` and `B4 = 0x05` — when this appears in the body the parser flushes the current paragraph and sets `Paragraph.space_before = True` on the following paragraph. Confirmed across 36 files and all ctrl_byte variants (0x61, 0x6d, 0x68, 0x66, 0x64, 0x63, 0x62, 0x60); it is the standard LocoScript 2 mechanism for inserting a visual section gap (blank line) between major document sections. Converters render `space_before` as an empty `''` TXT entry (double blank-line gap), a `\pard\par` RTF paragraph, or a DOCX `add_paragraph()`. A page-break variant adds `B5 = 0x07`, which also triggers a jump past the binary layout block that follows.

**Pre-body structural transition blocks (`B3=0xe8`, `B4=0x05`):** The same `e8 05` signature also appears in the pre-body zone (before `body_start`) as empty section-boundary markers. These are NOT paragraph breaks — the block is followed by binary metadata (not body text). When `i < body_start` and the block has `B3=0xe8`, `B4=0x05`, the parser jumps directly to the next `para_ctrl` to skip all binary payload and prevent it leaking into the header. Confirmed in MEMORIAL.002 pre-body zone (0x5ed–0x76d).

**Structural page-break blocks in `22 6d` / `22 42` body (non-`0x61` ctrl_byte only):** In `22 6d` variant files (e.g. BREWERS.5), page boundaries within the body are marked by structural blocks with `B3 ≥ 0x80`, `B4 = 0x0e`, `B5 = 0x07`, `B6 = 0x03` — i.e. `a6 0e 07 03` in the B3–B6 bytes. These are handled in the main parse loop (not `_skip_ctrl_sequence`) after the standard structural-header skip is applied: `flush_run(); flush_para(); current_para.page_break_before = True`, then jump to the next `22 ctrl 0b`. Scoped to `ctrl_byte ≠ 0x61`: standard `22 61` files use `0e 01`/`0e 02` for page breaks and their structural blocks (e.g. `c4 0e 07 03`) must not trigger a page break here. Confirmed in BREWERS.5 (12 page breaks). Investigation documented in `Header Footer Investigation v2.md` (local only).

### Other Control Types
All other control types (`0c`, `0d`, `36`, etc.) follow a variable-length structure: skip the 2-byte prefix + type byte + 1 extra parameter byte (4 bytes total), then consume any additional non-printable parameter bytes (excluding `02` word separators and `13` which may begin a formatting sequence), then skip any doubled-pair indent markers.

**Self-referential sequences — `22 XX XX` (type == ctrl_byte):** When the control type byte equals the ctrl_byte itself (e.g. `22 61 61` in standard files, `22 6d 6d` in `22 6d` variant files), the sequence is always binary layout/page metadata and never contains body text. The parser skips directly to the next `22 XX 0b` paragraph content block rather than using the variable-length skip, which would otherwise stop at the first printable byte and leak binary data as text artefacts.

**Self-referential skip + preceding paragraph break:** When a self-referential `22 XX XX` sequence jumps to a target `22 XX 0b` block, the two bytes immediately before the target block are checked for `0f 02` (paragraph break). If found, `flush_run()` and `flush_para()` are called before the jump, preserving the paragraph boundary that the direct jump would otherwise bypass. Confirmed in MEMORIAL.002 at 0x15bd (`22 61 61` jump bypasses `0f 02` at 0x15de).

**SOH doubled-pair structural marker — `01 XX XX` (3 bytes):** A `SOH` byte (`0x01`) followed by two identical printable bytes is a structural indent/layout marker. It appears in binary metadata sequences (e.g. after variable-length skips that stop at a `WORD_SEP`) and must be consumed silently. Detected in the main parse loop as `data[i] == 0x01 and data[i+1] == data[i+2] and data[i+1] >= min_dp`.

**Column/layout spec — `0c XX 01 YY 01 ZZ` (6 bytes):** FF (`0x0c`) followed by a printable byte and `0x01` identifies a structural column/section layout parameter. The printable byte (e.g. `0x24` = '$', `0x23` = '#') would otherwise be emitted as text. Distinguished from legitimate `0c word` sequences where the byte after the printable char is NOT `0x01`. Skip 6 bytes. Confirmed in MEMORIAL.002 at 0x1188 and 0x15b1.

## Trailing Indent Metadata Pattern

After many control sequences a 4-byte metadata suffix appears:

```
00 01 XX XX    (where XX == XX and XX > 0)
```

The two identical bytes are a doubled-pair indent marker encoding the paragraph's left margin. This suffix is consumed after any `13 04 xx` font-size command and after any `22 61` control sequence skip.

The threshold is `XX > 0` (not `XX >= 0x20`). Values below `0x20` (e.g. `0x0e = 14`) are valid indent amounts in all file variants and must be consumed to prevent the following bytes from being misinterpreted as control codes. The original `>= 0x20` threshold caused `00 01 0e 0e 0e 02` to leave `0e 02` visible to the section-break handler (confirmed in BUILDNGS.H). Using `> 0` also correctly consumes low-value pairs in `1e 74` variant files (e.g. `00 01 06 06`), avoiding spurious content artifacts.

## Doubled-Pair Indent Markers

Throughout the format, indent and margin values are encoded as a pair of identical printable bytes (e.g. `4a 4a` = 'JJ', `47 47` = 'GG', `3d 3d` = '==', `54 54` = 'TT'). These are structural metadata, never text content. They appear at the tail of paragraph content blocks and after various trailing metadata sequences.

## Document Structure (Typical)

```
[DOC header — page layout, section metadata]
22 61 0b ...   ← first paragraph content block (content start anchor)
[text bytes, 02 separators, 13 04 xx formatting codes]
0f 02 22 61 0b ...   ← paragraph break
22 61 0b ...   ← next paragraph content block
...
0e 01 / 0e 02  ← section/page break + binary layout block
22 61 0b ...   ← paragraph content resumes after section break
...
```
