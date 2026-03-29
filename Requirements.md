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
- Converted files will be named the same as the input file with the new extension 
- If during conversion an existing file is found, then the Application should create a prompt asking the user for input
- Where a file already exists a user can chose to skip conversion or overwrite the exiting file. If running a batch, the user can also chose to "skip ALL overwrites" or "Yes to ALL overwrites"
- If a batch conversion is complete a success message is shown with the time taken and the count of files processed
- Files to be converted will have no file extension

# Errors
- If when processing multiple files a file fails, the error should be logged in a .txt file and processing should move to the next file
- The error log should be saved in the same directory as the file being processed
- The error log should be named "DocConvertor-Error.log"
- The error log should be appended to on each run
- An error log entry should consist of: <TIMESTAMP> - <DocumentName>: Full Error Message
- If one or more files fail during a batch run an error message should be shown stating the number failed and directing the user to investigate the error log. 
- If an input file is not recognised as a valid Locoscript 2 format, treat it as a conversion error



---

# Known Limitations

These are issues that are understood but not yet resolved. They are good candidates for future work.

## First paragraph / document header
The very first paragraph in the output typically contains junk from the document header area — page layout metadata, section-control bytes, and the Locoscript version string (e.g. `== PCND 4.1...`). The parser skips to the first `22 61 0b` content marker, but the header structure before the first real paragraph is complex enough that some binary artefacts still leak through. This affects only para[0] and does not impact the body of the document. A future fix would identify and skip the full header block before content parsing begins.

## Untested document types
The parser was developed and validated against a single sample document (a research notes file). Locoscript 2 supported different document types (letters, labels, etc.) which may use different page-layout structures or section-break patterns not yet seen. New files may surface unrecognised `22 61 0b` variants or other control sequences — see the debugging workflow in `CLAUDE.md`.

## Overwrite prompt in batch mode
The current overwrite prompt (skip / overwrite) does not yet support "skip ALL" or "overwrite ALL" for batch conversions, as specified in the requirements. Each conflicting file prompts individually.

---

# Shadow Copy Mode

## Overview
An optional mode in the application that mirrors an entire folder structure, producing converted versions of all Locoscript 2 files found within it.

## Requirements

- The application shall provide a "Create processed shadow copy" option in the UI
- The user selects a source folder (rather than individual files)
- The application traverses the full folder structure recursively, locating all Locoscript 2 files (files with no extension)
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

Every valid Locoscript 2 file begins with the three-byte ASCII magic number `44 4f 43` ("DOC"). Files have no extension. Content parsing begins at the first occurrence of the paragraph content marker `22 61 0b` — everything before it is a document header containing page layout and section metadata that is not needed for text extraction.

## Byte Encoding

Body text is stored as raw bytes in the range `0x20–0x7E` (printable ASCII). Characters outside this range are control codes or structural metadata. There is no multi-byte character encoding for extended characters in the files studied; unmappable bytes are substituted with `?`.

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
Five bytes total. Emits a tab character (`\t`) in the output. The two trailing bytes are indent parameters and are consumed but not output.

### Indent Metadata — `09 00 01` [+ doubled printable pair]
A variant tab/indent marker that appears as trailing metadata after content bytes. The three-byte prefix is always consumed. If the next two bytes are identical printable characters (`>= 0x20`) they are also consumed as a doubled-pair indent marker.

### Section / Page Break — `0e 01` or `0e 02`
A two-byte sequence where `0e` is followed by `01` (section break) or `02` (page break). This is followed by a variable-length binary metadata block encoding the new section's page layout. The entire block is skipped by jumping forward to the next `22 61 0b` paragraph content marker. Content accumulated up to this point is flushed as a complete paragraph before the skip.

### Hyphen / Extra Space — `06`
Contextual byte. Emits a hyphen (`-`) when it falls between two printable text characters. Emits a space when adjacent to a word separator (`02`), another `06`, or a non-printable preceding byte.

## Control Sequence Prefix — `22 61`

The two-byte sequence `22 61` introduces a structured control sequence. The third byte is the control type. The prefix is also the literal opening of the typographic double-quote string `"a` in the document body (e.g. `"a typical example"`): when the byte immediately following `22 61` is a word separator (`02`) or `06`, the sequence is treated as literal text rather than a control code.

### Control Type `0b` — Paragraph Content Block
This is the most important control type. It marks the start of a new paragraph's content area and is used as a navigation anchor throughout the parser. The full structure is 8 bytes:

```
22 61 0b | B3 B4 B5 | B6 B7
          3 param    2 indent
```

Several structural variants exist:

| Condition | Meaning | Action |
|---|---|---|
| `B6 B7` = `13 04` | Formatting prefix immediately follows — leave for main loop | Skip 6 bytes |
| `B6..B8` = `78 00 01` | Extended indent variant; followed by a doubled printable pair | Skip 11 bytes |
| `B3 B4` = `c4 0e` | Structural section-header block; never contains body text | Skip to next `22 61 0b` |
| `B4 B5 B6` = `0a 09 00` | Tab-indent variant; followed by `01` + doubled printable pair | Skip 11 bytes |
| `B7 B8` = `13 04` | Formatting prefix one byte later — leave for main loop | Skip 7 bytes |
| `B7 B8` = `22 61` | Nested control prefix at indent position — leave for main loop | Skip 7 bytes |
| (default) | Standard 8-byte block | Skip 8 bytes |

### Other Control Types
All other control types (`0c`, `0d`, `36`, etc.) follow a variable-length structure: skip the 2-byte prefix + type byte + 1 extra parameter byte (4 bytes total), then consume any additional non-printable parameter bytes (excluding `02` word separators and `13` which may begin a formatting sequence), then skip any doubled-pair indent markers.

## Trailing Indent Metadata Pattern

After many control sequences a 4-byte metadata suffix appears:

```
00 01 XX XX    (where XX == XX and XX >= 0x20)
```

The two identical printable bytes are a doubled-pair indent marker encoding the paragraph's left margin. This suffix is consumed after: `13 04 50` (paragraph break), `13 04 64` (italic on), `13 04 78` (line break/italic off), and after any `22 61` control sequence skip.

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
