# Font Size and Paragraph Indent Investigation

This document investigates the binary signals for font size changes and paragraph left-indentation across two files:
- **BINDINDX.HEX** (`1e 74` variant index file) — indented sub-entries with smaller font
- **HENCOTES** (`22 61` standard file) — "Hex. Cour." citation paragraphs with indent and possible font change

---

## Part 1 — BINDINDX.HEX

### 1.1 Confirmed: Font size from B5/B6 in `1e 74 0b` block header

Already documented in BINDINDX-Investigation.md §Issue 7. Recap:

When B5=`0x14` in the paragraph block header, B6 encodes the font size (× 0.1pt):

| B5   | B6     | pt size | Appearance |
|------|--------|---------|------------|
| `14` | `0x78` | 12pt    | Small/italic sub-entries |
| `14` | `0x90` | 14.4pt  | Normal/large top-level entries |

Confirmed entries:
- **12pt (sub-entry):** "Abbey Court", "Addison, Mr. J.", "Alexander, Joseph & Co.", "Green Bank - see Abbey View"
- **14.4pt (top-level):** "Abbey Flags footpath", "Alemouth Road", "Alexander Place", "Green Belt"

### 1.2 New finding: B4 as indent-level indicator

Beyond the explicit B5=`0x14` / B6 font signal, many paragraph blocks have B5≠`0x14` — yet the user confirms their entries ARE visually indented. A consistent pattern in B4 separates top-level from sub-entries:

| B4 value | Entry | Visual level |
|----------|-------|--------------|
| `0x0f`   | Abattoir | Top-level |
| `0x0e`   | Alemouth Road (also B5=`14`, B6=`90`) | Top-level |
| `0x0d`   | Abbey Flags footpath (also B5=`14`, B6=`90`), Acts of Parliament | Top-level |
| `0x0c`   | Abbey Court (also B5=`14`, B6=`78`) | Sub-entry (indented) |
| `0x0b`   | Agricultural show, Albert Edward Club, Aldi | Sub-entry (indented) |
| `0x0a`   | Abbey View | Sub-entry (indented) |
| `0x09`   | Addison (also B5=`14`, B6=`78`) | Sub-entry (indented) |
| `0x08`   | Ainsley and Graham | Sub-entry (indented) |

**Proposed rule:** B4 ≥ `0x0d` → top-level (no indent); B4 ≤ `0x0c` → sub-entry (apply left indent).

This rule works for all entries examined without requiring the B5=`0x14` font signal. The B4 value may encode a LocoScript "layout slot" or text column position; lower values correspond to paragraph blocks positioned further left in the ruler system (which in a column-index layout means they are physically indented further right on the page).

**Caution:** this threshold (`0x0d`) is derived from the Abbey entries only. It should be verified against more sections of the document before hardcoding. A safer implementation might use the `0x0c` threshold (only B4 ≤ `0x0c`), since B4=`0x0d` appears for confirmed top-level entries (Acts of Parliament).

### 1.3 Italic inheritance across paragraphs

In `1e 74` files, paragraph boundaries are signalled by `0f 02 1e 74 0b` (separator) rather than `13 04 50`. The `flush_para` call at a `0f 02` separator does NOT reset the `italic` state. Italic therefore carries forward across paragraphs.

Pattern for a sub-entry group:
1. **Group opener** (B5=`14`, B6=`78`): block header + `13 04 64` (italic-on) + text + *no* `13 04 78` before the `0f 02` separator → italic remains ON
2. **Subsequent entries** (no `13 04 64`, B5≠`14`): inherit italic=True from group opener → render italic
3. **Last entry in group**: ends with `13 04 78` (italic-off) → italic=False
4. **Top-level entry** that follows: italic=False → renders non-italic

Example trace (0x866 – 0x985):
```
0x869: 1e 74 0b e2 09 14 78 00  ← Addison block (B4=09, B5=14, B6=78 → 12pt sub-entry)
0x871: 13 04 64 00 01 32 32      ← italic-on, trailing indent
"Addison, Mr. J.; Family Grocer - see Market Street"
0x8A5: 0f 02                     ← separator (italic NOT reset)
0x8B5: 1e 74 0b 44 0b 01 28 28  ← Agricultural show (B4=0b, B5=01 — no font signal)
"Agricultural show - see Bridge End Parks"
0x8E3: 0f 02                     ← separator (italic stays True)
0x8E5: 1e 74 0b 16 08 01 41 41  ← Ainsley (B4=08, B5=01)
"Ainsley and Graham; Painters, Gilders, Glaziers - see Fore Street"
0x92D: 0f 02                     ← separator (italic stays True)
0x92F: 1e 74 0b e4 0b 01 23 23  ← Albert Edward Club (B4=0b, B5=01)
"Albert Edward Club - see Hall Garth"
0x958: 0f 02                     ← separator (italic stays True)
0x95C: 1e 74 0b 8c 0b 01 27 27  ← Aldi (B4=0b, B5=01)
"Aldi - see Haugh Lane Industrial Estate"
0x984: 13 04 78                  ← italic-off (end of group)
0x990: 1e 74 0b 4c 0e 14 90 00  ← Alemouth Road (B4=0e, B5=14, B6=90 → 14.4pt top-level)
"Alemouth Road"  ← italic=False ✓
```

### 1.4 The doubled-pair trailing indent is NOT a left indent

The doubled-pair values in BINDINDX.HEX (from `00 01 XX XX` or `01 XX XX` trailing metadata) are large absolute numbers:
- Abbey Court: `1e 1e` = 0x1e × 120 = 3600 twips (2.5")
- Addison: `32 32` = 0x32 × 120 = 6000 twips (4.2")
- Abbey View: B6/B7 `24 24` = 0x24 × 120 = 4320 twips (3.0")

These are inconsistent between entries at the same visual indent level, and far too large to be left indent values. They appear to be LocoScript-internal ruler position markers (possibly measuring absolute cursor position from the left edge of the page, used by the LocoScript rendering engine). They should NOT be used as left indent values for RTF/DOCX output.

### 1.5 Proposed indent amount for sub-entries

Since the doubled-pair gives no useful indent information, and the visual indent from the JPEG is approximately 0.4 inches, the recommended implementation is:

**Fixed indent: 576 twips (0.4") for all identified sub-entries.**

This should be applied when:
- B4 ≤ `0x0c` in the `1e 74 0b` block header (confirmed top-level/sub-entry boundary), **OR**
- Italic state is True at the start of a new `1e 74 0b` paragraph body block (inheriting from group opener)

Both conditions should produce the same indent, but using both as a cross-check avoids edge cases.

### 1.6 Font size for sub-entries without explicit B5/B6 signal

When a sub-entry has B5=`0x01` (no font signal), it's part of an inherited-italic group whose opener had B5=`14`, B6=`0x78`. The appropriate output font size is **12pt** (inherited from the group opener). One approach:
- Track `current_font_size: float | None` at parse time
- When B5=`14`, update `current_font_size = data[i+6] / 10.0`
- Reset to `None` at `13 04 78` (italic-off = end of group) or when top-level block (B4 ≥ `0x0d`) fires

---

## Part 2 — HENCOTES

### 2.1 `08 05 01 XX XX` as paragraph left indent

The "Hex. Cour." paragraphs in HENCOTES start with `08 05 01 XX XX` (PARA_INDENT), which the parser currently discards. The doubled-pair value XX is different for each paragraph:

| Doubled pair (XX) | Value | Twips (× 144) | Inches | Example paragraph |
|-------------------|-------|---------------|--------|-------------------|
| `0a 0a` | 10 | 1440 | 1.00" | "Hex. Cour. 6.3.2015 - 100 Years Ago." |
| `05 05` | 5  | 720  | 0.50" | "Hex. Cour. 4.11.1994 - 75 Years Ago." |
| `0a 0a` | 10 | 1440 | 1.00" | "Hex. Cour. 10.2.1967 - to March 14th 1936." |

(HENCOTES scale pitch = `0x18` = 24 decimal; twips_per_unit = 24 × 6 = 144.)

The **different values for different paragraphs** indicate the document genuinely uses two indent levels for the citation lines — not a single fixed indent. The `08 05 01 XX XX` doubled-pair IS the left indent in scale-pitch units.

**Proposed rule for `22 61` files:** when `08 05 01 XX XX` fires, record `XX × _twips_per_unit` as `current_para.left_indent`. This replaces the current "consume silently" behaviour.

Hex evidence (0x855):
```
00000850: 5000 0805 010a 0a48 6578 2e02 436f 7572 ...
         [P.][08 05 01 0a 0a] H e x . . C o u r
```

Hex evidence for second Hex. Cour. (0x8F2):
```
000008f0: 5000 0805 0105 0548 6578 2e02 ...
         [P.][08 05 01 05 05] H e x . .
```

### 2.1b `08 05 01 XX XX` doubled-pair distribution in HENCOTES

Surveying all 60 occurrences of `08 05 01 XX XX` in HENCOTES:

| XX value | Count | Twips | Inches | Notes |
|----------|-------|-------|--------|-------|
| `0x0a`   | 22    | 1440  | 1.00"  | Most common — Hex. Cour. indent |
| `0x09`   | 16    | 1296  | 0.90"  | Second most common |
| `0x11`   | 4     | 2448  | 1.70"  | Deeper indent level |
| `0x05`   | 4     | 720   | 0.50"  | Shallow indent — second Hex. Cour. |
| `0x06`   | 2     | 864   | 0.60"  | |
| `0x0c`   | 2     | 1728  | 1.20"  | |
| `0x20`   | 1     | —     | —      | **Outlier** — see below |
| `0x24`   | 1     | —     | —      | **Outlier** — see below |
| `0x3a`   | 1     | —     | —      | **Outlier** — see below |
| (others) | 7     | varies|        | |

**Outlier context:**
- `0x3a` ("::") at 0x1d83: `"...gins. [P] [08 05 01 3a 3a] Balderdash & Pi..."` — doubled-pair is ASCII `:`
- `0x20` ("  ") at 0x769:  `"...hens. [P] [08 05 01 20 20] The Place Names..."` — doubled-pair is ASCII space
- `0x24` ("$$") at 0x433d: `"...ther. [P] [08 05 01 24 24] Buildings of En..."` — doubled-pair is ASCII `$`

These outliers have XX ≥ `0x20` (the standard doubled-pair threshold for `22 61` files). They are NOT indent values — at 144 twips/unit, values like 0x3a × 144 = 8352 twips (5.8") would exceed the page width. They likely encode some other paragraph metadata (possibly a style tag or named style code in the LocoScript format), and the printable doubled-pair in each case is coincidental.

**Rule for PARA_INDENT left indent extraction:**
- If XX < `0x20` (i.e., below the standard doubled-pair threshold): treat as left indent → `XX × _twips_per_unit`
- If XX ≥ `0x20`: consume silently (as currently) — these are NOT indent values

This gives 57 genuine indent occurrences and 3 "other metadata" cases.

### 2.2 "Hex. Cour." is NOT italic

Contrary to the user's initial recollection, the "Hex. Cour." citation lines are NOT italic. Confirmed by byte analysis: no `13 04 64` (italic-on) appears within these paragraphs. The `13 04 78` sequence that follows "Years Ago." is a **line break** (not italic-off), since italic=False at that point.

Para 3 (4.11.1994) does have italic=True for one run, but this is from a `13 04 64` appearing mid-body in the continuation text ("1936. Looking back…"), not in the citation line itself.

### 2.3 Font size in HENCOTES — no explicit signal found

Unlike BINDINDX.HEX's B5=`0x14`, B6=XX encoding, no analogous font-size signal has been identified in HENCOTES's `22 61 0b` block headers. The paragraph blocks for "Hex. Cour." paragraphs have normal B5/B6 values (e.g. `01 0a 0a`, `01 05 05`).

Two hypotheses for the smaller font appearance:
1. **It is encoded** somewhere — possibly in the layout table (0x2C6) which includes point size at entry offset +13, and a different layout entry may apply to these paragraphs. Further investigation needed.
2. **It is NOT separately encoded** — the Hex. Cour. paragraphs may print at the same point size as the rest of the document. The user's impression of smaller font may come from the indentation making the line appear visually smaller, or the `Hex. Cour.` abbreviation being a smaller visual element than the body text.

Without a confirmed font signal, no font size change should be implemented for HENCOTES in this pass. Left indent from `08 05 01 XX XX` can still be implemented independently.

### 2.4 Structure of "Hex. Cour." paragraphs

The full structure (confirmed from hex):
```
13 04 50                        ← previous paragraph break
08 05 01 0a 0a                  ← PARA_INDENT (left indent = 0x0a × 144 = 1440 twips)
Hex. Cour.                      ← "Hex. Cour." (NOT italic)
09 05 01 1a 1a                  ← TAB_SEQ (tab stop at 0x1a × 144 = 3744 twips)
[word sep] 6.3.2015 [space] - [space] 100 Years Ago.
13 04 78                        ← LINE BREAK (NOT italic-off — italic=False here)
[continuation body text for the same paragraph]
13 04 50                        ← paragraph break (ends the paragraph)
```

The "Hex. Cour." abbreviation and the date/title occupy the first line; the citation body (historical extract) follows after the line break as part of the same paragraph.

---

## Part 3 — Cross-file comparison: PARA_INDENT in 22 61 files

The `08 05 01 XX XX` sequence appears in HENCOTES body paragraphs in two roles:
1. **Citation line indent** (0x0a or 0x05) — at the start of "Hex. Cour." paragraphs
2. **Section-heading style** (other values) — need to check other occurrences

Other occurrences in HENCOTES:
```
00001e10: ...1304 7800 0147 -> 0x08 05 01 47... 
```
It would be worth grepping all `08 05 01` values in HENCOTES to understand the full range, and whether there's a "0 indent" baseline value (e.g. `00 00`) that signals non-indented paragraphs. This would help confirm the unit system.

---

---

## Part 4 — Cross-file Verification (manual_tests/)

### 4.1 PARA_INDENT distribution across all files

`08 05 01 XX XX` (PARA_INDENT) occurrence counts by file:

| File | Most common XX | Total occurrences | Scale pitch | Notes |
|------|----------------|-------------------|-------------|-------|
| HENCOTES | `0x0a` (22×) | 60 | `0x18` (144 t/u) | "Hex. Cour." citations confirmed |
| BUILDNGS.A-C | `0x0a` (99×) | ~200 | `0x14` (120 t/u) | Same "Hex. Cour." pattern confirmed |
| BUILDNGS.D-G | `0x0a` (92×) | ~180 | (same file format) | |
| BUILDNGS.H | `0x0a` (108×) | ~200 | `0x18` (144 t/u) | |
| BREWERS.5 | `0x0a` (32×) | ~70 | `0x14` (120 t/u) | |
| MEMORIAL.002 | `0x0e` (4×) | 14 | | |
| BINDINDX.HEX | `0x06` (24×) | 53 | `0x14` (120 t/u) | `1e 74` body + prebody zone |

### 4.2 Cross-file confirmation: `08 05 01 0a 0a` before "Hex. Cour."

BUILDNGS.A-C also uses `08 05 01 0a 0a` before "Hex. Cour." citation text (confirmed at 0x156C, 0x15CF, 0x164A). BUILDNGS.A-C has scale_pitch=`0x14` (120 t/u), so the indent for these entries is 10 × 120 = 1200 twips ≈ 0.83". HENCOTES uses scale_pitch=`0x18` (144 t/u), giving 10 × 144 = 1440 twips = 1.00". Same 10-pitch-unit indent regardless of the actual character width — confirms this is a **pitch-unit measurement** not a fixed twip value.

### 4.3 XX ≥ 0x20 outliers: bibliography/reference paragraph style codes

Every single XX ≥ 0x20 occurrence across all files is followed by a **book or reference title**:

| File | XX | Chr | Text following |
|------|----|-----|----------------|
| HENCOTES | `0x20` | ` ` | "The Place Names of Hexham" |
| HENCOTES | `0x24` | `$` | "Buildings of England, Nor..." |
| HENCOTES | `0x3a` | `:` | "Balderdash & Piffle. One..." |
| BUILDNGS.A-C | `0x21` | `!` | "Parson & White's Director..." |
| BUILDNGS.A-C | `0x27` | `'` | "History and Directory of..." |
| BUILDNGS.H | `0x28` | `(` | "The Buildings of England,..." |
| BUILDNGS.H | `0x41` | `A` | "The Ancient Cathedral of..." |
| BREWERS.5 | `0x44` | `D` | "History, Topography, & Di..." |
| BREWERS.5 | `0x2b` | `+` | "An Historical Guide to He..." |
| BINDINDX.HEX | `0x27` | `'` | "Oxford Dictionary of Nati..." |
| BINDINDX.HEX | `0x24` | `$` | "The Stanegate Crossing of..." |
| BINDINDX.HEX | `0x37` | `7` | "Library Provision in Nine..." |

**Conclusion:** XX ≥ `0x20` in `08 05 01 XX XX` is a **bibliography/reference paragraph style code**. Different XX values may correspond to different visual styles for reference entries (italic, hanging indent, different font, etc.) in LocoScript's paragraph style system. The same XX value appears consistently for the same reference work across occurrences (e.g. `0x27` always precedes "Oxford Dictionary of National Biography" in BINDINDX). The current "consume silently" behaviour is correct — no indent should be applied. The true formatting for reference entries is a separate future investigation.

**Revised rule:**
- XX < `0x20`: left indent signal → `current_para.left_indent = XX × _twips_per_unit`
- XX ≥ `0x20`: bibliography/reference style code → consume silently (as currently)

### 4.4 MEMORIAL.002 — hierarchical indentation in inscription text

MEMORIAL.002 (scale_pitch=`0x18`, twips_per_unit=144) has 14 occurrences of `08 05 01 XX XX`, all with XX < `0x20`:

| XX | Twips | Inches | Context |
|----|-------|--------|---------|
| `0x04` | 576 | 0.40" | "June" (month sub-entry) |
| `0x05` | 720 | 0.50" | "(ST. JULIEN)" sub-entry |
| `0x07` | 1008 | 0.70" | "Aug-Nov" month entry |
| `0x08` | 1152 | 0.80" | "May-July" month entry |
| `0x09` | 1296 | 0.90" | "April-May" month entry |
| `0x0a` | 1440 | 1.00" | "1918 March" year entry |
| `0x0e` | 2016 | 1.40" | "1915 April-May", "1916-7 Aug-Jan" year entries |
| `0x10` | 2304 | 1.60" | "1915-6 Dec-March" year entry |
| `0x11` | 2448 | 1.70" | "1916 April-July" year entry |

This is the war memorial inscription (right-hand plaque), formatted as a chronological battle list. The different indent values reflect LocoScript's column ruler positions for the multi-level list. **No XX ≥ 0x20 outliers** — all 14 occurrences are genuine indent signals. Findings hold for MEMORIAL.002.

### 4.5 BINDINDX-specific: PARA_INDENT dominant value = 0x06

BINDINDX.HEX's dominant PARA_INDENT value is `0x06` (24 occurrences). At twips_per_unit=120: 6 × 120 = 720 twips ≈ 0.5". This is close to the visually-estimated 0.4" sub-entry indent from the JPEG.

These `08 05 01 06 06` sequences appear throughout the 1e-prefix body stream and likely precede most sub-entry paragraphs. This provides a **direct indent signal** for BINDINDX sub-entries that complements the B4/B6 block-header analysis from Part 1.

**Revised proposal for BINDINDX:** use `08 05 01 XX XX` (XX < 0x20 → left_indent = XX × 120) as the primary indent signal. Reserve the B4 heuristic as a secondary check for entries with no PARA_INDENT (where the block header B4 ≤ 0x0c indicates sub-entry level).

### 4.5 Font size signals in BUILDNGS / MEMORIAL

No analogous B5=`0x14`, B6=font-size encoding has been found in BUILDNGS or MEMORIAL blocks. These files appear to be single-font documents. The font-size signal remains specific to `1e 74` variant files.

---

## Summary of Proposed Changes

### `parser.py`

**1. Add `left_indent: int` and `font_size: float | None` to `Paragraph`:**
```python
@dataclass
class Paragraph:
    runs: list[TextRun] = field(default_factory=list)
    alignment: str = 'left'
    tab_stops: list[int] = field(default_factory=list)
    left_indent: int = 0            # in twips (0 = no indent)
    font_size: float | None = None  # in points (None = inherit document default)
```

**2. HENCOTES / 22 61 files — `08 05 01 XX XX` handler:**
```python
# --- Paragraph indent marker: 08 05 01 + 2 param bytes ---
if data[i:i+3] == PARA_INDENT:
    xx = data[i + 3] if i + 3 < n else 0
    if xx > 0:
        current_para.left_indent = xx * _twips_per_unit
    i += 5
    continue
```

**3. BINDINDX / 1e-prefix files — sub-entry detection:**
In the `ctrl_type == 0x0b` body-block handler, when `prefix_byte != 0x22`:
- If B4 (= `data[i+4]`) ≤ `0x0c` → `current_para.left_indent = 576` (0.4")
- If B5=`0x14` and B6=`0x78` → `current_para.font_size = 12.0`
- If B5=`0x14` and B6=`0x90` → `current_para.font_size = 14.4`

Font size inheritance across paragraph boundaries (for entries without B5=`0x14`):
- Introduce `_current_font_size: float | None` (parse-local variable)
- Update on B5=`0x14` blocks; reset to `None` on top-level block (B4 ≥ `0x0d`)
- Apply to `current_para.font_size` if set

### `converter.py`

**RTF:**
- Left indent: `\li{twips}` in the `\pard` line
- Font size: `\fs{half_pts}` (twips * 2 / 20 = point × 2) before run text

**DOCX:**
- Left indent: `paragraph.paragraph_format.left_indent = Pt(left_indent / 1440)`
- Font size: `run.font.size = Pt(font_size)`

---

## Open Questions (before implementation)

1. **B4 threshold in BINDINDX**: is `0x0d` consistently the boundary between top-level and sub-entry across the full document? Verify with more entries (especially mid-document).
2. **Font size inheritance across `0f 02` boundaries**: does resetting `_current_font_size` at top-level blocks produce the right results for all sub-entry groups, or do some groups span multiple top-level markers?
3. **HENCOTES font size**: is there any font-size signal in `22 61` body stream? (Layout table entry with explicit pt size per paragraph?) Or is font size invariant throughout the document?
4. **DOCX indent unit**: `Twips(n)` in python-docx returns a valid `Length` in EMU and is accepted by `paragraph_format.left_indent`. Confirmed: `Twips(576)` = 365,760 EMU ✓.
5. **Manual test files**: verify findings against BUILDNGS, MEMORIAL, and other files in `manual_tests/` before implementation.
