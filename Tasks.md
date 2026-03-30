# Tasks

## Colleague's Findings — Investigate & Potentially Implement

These items come from additional Locoscript 2 research and are not currently handled by the parser. Each needs investigation against real sample files before implementing.

## Known Limitations (future work)

- [ ] **High-byte character mappings (0x80–0xFF)** — Locoscript 2 uses the Amstrad CP/M Plus character set, which differs from Latin-1/Unicode for bytes above 0x7F. Currently all unrecognised high bytes are silently skipped. The colleague's document flags `0xC3` → è and `0xB4` → é as known mistranslations. The full mapping table is at https://en.wikipedia.org/wiki/Amstrad_CP/M_Plus_character_set. Implementing this would significantly improve character fidelity across the sample set.

- [ ] **RTF page size** — RTF output does not currently set page dimensions. A4 = 11906 × 16838 twips (from colleague's document). Adding `\paperw11906\paperh16838` and appropriate margin settings would produce correctly-sized RTF output.

- [ ] **Paragraph alignment (centre/right)** — DC1 (`0x11`) and DLE (`0x10`) appear to be centre and right-alignment control sequences respectively (colleague's document, "Control Sequences" section). Not yet decoded or handled by the parser. Investigate against sample files before implementing.

- [ ] **Tab handling in converter output** — The parser correctly emits `\t` for `0f 04` tab sequences, but all three converters call `.strip()` on run/paragraph text, which drops leading/trailing tabs. RTF output also passes `\t` as a raw character rather than the `\tab` control word. DOCX strips tabs from run text entirely. Improve converter fidelity for tab characters in TXT, RTF, and DOCX output.

- [ ] **JOY format parser** — 233 JOY files in the sample set cannot currently be converted. Two sub-versions exist: `01 04` (word sep `0x0a`, para break `07 02 0a 55 0e XX YY 06 ZZ ZZ`) and `01 02` (word sep `0x01`, different structure). Implementing proper support would require a separate parser alongside the existing DOC parser.

- [ ] **Untested document types** — Parser was developed against a single sample file. Locoscript 2 letters, labels, and other document types may surface unrecognised control sequences.

- [x] **Remove "no file extension" restriction** — Updated Requirements.md: input files may have any extension or none. Shadow Copy mode spec updated to identify files by `DOC` magic bytes rather than absent extension. No code changes needed — the app already handles both cases correctly.

- [ ] **Shadow Copy mode** — New application mode to mirror-convert an entire folder structure. See Requirements.md for full spec. Do this last.

## Completed

- [x] **Detailed file header map** — Investigated. Summary field (0x05–0x5E) contains template descriptions, not document titles — not useful. Version bytes always `01 03` — not useful. Font table at `0x138` (10 × 28 bytes) confirmed with font names ("CG Times", "LX Roman" etc.) but font references in the text stream have not been identified, so font mapping is blocked for now. Layout table at `0x2C6` (10 × 73 bytes) confirmed: scale pitch at entry offset +11 (`0x18` = 10cpi = 0.1 inch/unit), point size at +13 (pt × 10, `0x78` = 12pt), 15 tab stop positions at +33–+47 (scale pitch units; `0x18` = default 2.4", custom values confirmed). Document-level margins appear around `0x2B8` (two 16-bit fields, `0x28` or `0x30` across files) but unit system unconfirmed — left unresolved. Tab stop extraction feeds into the tab handling task. First-paragraph junk unaffected.
- [x] **Set up repo on GitHub** — Remote repository created at github.com/MrTimLee/locoscript_convertor. GitHub CLI (`gh`) authenticated for raising PRs.
- [x] **`08 05 01 XX XX` doubled-pair artefacts** — Fixed in branch `fix/paragraph-indent-artefacts`. Added `PARA_INDENT` handler consuming all 5 bytes. Golden fixture regenerated. 23/23 tests passing.
- [x] **Batch overwrite: "Skip ALL" / "Overwrite ALL"** — Implemented in branch `feature/batch-overwrite-all`. Custom 4-button dialog (Yes / No / Yes to All / Skip All); batch buttons only shown for multi-file conversions. Policy state reset on each new run. 23/23 tests passing.
- [x] **Show time taken in completion message** — Implemented in branch `feature/completion-time`. Elapsed time recorded with `time.monotonic()` and shown in both the summary dialog and status bar. 23/23 tests passing.
- [x] **First paragraph junk** — Implemented in branch `fix/first-paragraph-header-junk`. `_find_content_start` now iterates through `22 61 0b c4 0e` structural header blocks, skipping across section breaks to land on the first real content paragraph. Improved 185/443 sample files, 0 regressions. 23/23 tests passing.
- [x] **`0xE9` = `£` symbol** — Implemented in branch `feature/e9-pound-sign`. Added extended character mapping in the main parse loop. Golden fixture regenerated. 24/24 tests passing.
- [x] **Bold, underline, superscript, subscript** — Implemented in branch `feature/bold-underline-formatting`. Extended `TextRun` with bold/underline/superscript/subscript flags. Added `08 XX`/`09 XX` inline formatting handler in parser. RTF output uses `\b`/`\b0`, `\ul`/`\ulnone`, `\super`/`\nosupersub`. DOCX output sets `run.bold`, `run.underline`, `run.font.superscript`. Confirmed bold in real sample files (BOOTSHEX.HAM). 33/33 tests passing.
- [x] **`0x0F` (SI) sequences — line/paragraph structure** — Implemented in branch `feature/si-sequences`. `0f 04` (tab) and `0f 05` (hanging indent) had printable param bytes leaking as artefacts. Added handlers consuming params and emitting `\t` for `0f 04`. 27/27 tests passing.
- [x] **`0x05` (ENQ) — extended character encoding** — Implemented in branch `feature/enq-extended-characters`. Added `_ENQ_CHAR_MAP` and 5-byte handler (`05 base 01 diacritic 01`). Maps `(0x63, 0x13)` → ç (confirmed in "façade", "Français"). Trailing doubled-pair indent consumed to prevent 'FF'/'DD' artifacts. 38/38 tests passing.
- [x] **"JOY" magic word** — Investigated. 233 JOY files in sample set (34% of total). Two sub-versions with different word separators and paragraph structures; no `22 61 0b` anchor. Informative `ParseError` added. Full JOY parser added to Known Limitations. 39/39 tests passing.
