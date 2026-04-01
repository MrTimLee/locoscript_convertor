# Tab Stop Investigation

This document records everything discovered during investigation of tab stop position preservation, to inform implementation. Primary investigation files: **HENCOTES**, **A4Letter**, **Brewers5**, and **Memorial.002**. Additional reference material in `Additional info/SITabSettings.xlsx` (colleague's investigation notes) and the corresponding RTF outputs and hex dumps in that folder.

---

## Goal

Preserve the author's intended tab stop positions when converting to RTF and DOCX. Currently all `\t` characters in the output fall at Word/LibreOffice default tab stops (every 0.5"), which differs from the original LocoScript 2 layout and produces visible alignment errors — most notably an oversized gap in HENCOTES.

---

## Tab Sequences in Locoscript 2

There are two distinct binary sequences that produce tab characters in the output.

### `09 05 01 XX XX` — Inline Citation Tab

Structure: 5 bytes — `09 05 01` prefix + 2 param bytes. Currently handled in the parser as `TAB_SEQ`, which emits `\t` and discards all 5 bytes.

**Finding:** The doubled param bytes `XX XX` directly encode the **target column position** in scale pitch units, measured from the left margin. At 10cpi (scale pitch `0x18`): position = `XX × 0.1"`.

Evidence from HENCOTES:
- `09 05 01 1c 1c` at 0x078E: `0x1c` = 28 → target column = **2.8"**
- `09 05 01 1a 1a` at 0x086F: `0x1a` = 26 → target column = **2.6"**
- `09 05 01 10 10` at 0x0B1B: `0x10` = 16 → target column = **1.6"**
- `09 05 01 3c 3c` at 0x3F52: `0x3c` = 60 → target column = **6.0"**

The values vary widely (8–60) across the document, confirming they are position values rather than slot indices.

### `0f 04 B1 B2` — SI Hanging-Indent Tab

Structure: `0f 04` prefix, optionally followed by non-printable param bytes, then two printable bytes B1 and B2, then optional `01 ZZ ZZ` trailing indent. Currently handled in the parser as the `0f 04` branch of the SI sequence handler, which emits `\t` and discards B1 and B2.

**Finding:** 
- **B2** = the body ctrl_byte of the file. It acts as a structural delimiter confirming the byte boundary.
- **B1** = the intended tab/indent column position in scale pitch units.

| File | ctrl_byte | Example sequence | B1 | B2 | Column at 10cpi |
|------|-----------|-----------------|----|----|-----------------|
| A4Letter | `0x61` | `0f 04 27 61` | `0x27` = 39 | `0x61` | 3.9" |
| A4Letter | `0x61` | `0f 04 4f 61` | `0x4f` = 79 | `0x61` | 7.9" |
| Brewers5 | `0x6d` | `0f 04 23 6d` | `0x23` = 35 | `0x6d` | ~3.5" |
| Memorial.002 | `0x42` | `0f 04 2a 42` | `0x2a` = 42 | `0x42` | 4.2" |
| Memorial.002 | `0x42` | `0f 04 31 42` | `0x31` = 49 | `0x42` | 4.9" |

A4Letter uses 4 `0f 04` sequences in a row before the address block content (`0x27 0x2c 0x31 0x4f`), defining 4 column stops. After all 4 tabs, content (e.g. "1 St. Acca's Court") begins. The RTF output from the colleague's tool renders this as `\tab \tab \tab \tab [content]`, aligning the text to the right side of the page.

---

## Layout Table Tab Stop Values

The layout table at `0x2C6` contains 10 × 73-byte entries. Each entry has:
- **Offset +11**: scale pitch byte (`0x18` = 10cpi = 0.1 inch per scale pitch unit)
- **Offset +13**: point size × 10 (`0x78` = 12pt)
- **Offsets +33..+47**: 15 tab stop position values, in scale pitch units

### HENCOTES (all default)

All 10 entries identical:

| Slot | Value | Position at 10cpi |
|------|-------|-------------------|
| 0    | `0x00` | — (unused/zero) |
| 1–14 | `0x18` | 2.4" each |

All tab stops are the LocoScript default spacing of 2.4". No custom stops.

### Memorial.002 (custom tab stops confirmed)

All 10 entries identical (except entry 9 which is offset by 1 slot):

| Slot | Value | Position at 10cpi |
|------|-------|-------------------|
| 0    | `0x00` | — (unused/zero) |
| 1    | `0x27` = 39 | **3.9"** (custom) |
| 2    | `0x2c` = 44 | **4.4"** (custom) |
| 3    | `0x31` = 49 | **4.9"** (custom) |
| 4–14 | `0x18` | 2.4" each (default) |

The `0f 04 B1 B2` B1 values in Memorial (0x2a, 0x2f, 0x30, 0x31, 0x32, 0x33) cluster around 4.2"–5.1" at 10cpi, straddling the custom layout stops at 3.9", 4.4", 4.9". The B1 values are NOT restricted to the layout table slots — they are direct column positions, potentially snapping to or extending beyond the defined stops.

### A4Letter and Brewers5

Both show all-default tab stops (`0x00` + fourteen × `0x18`). A4Letter's `0f 04` sequences use B1 values (0x27–0x4f) that are larger than any single layout-table default (0x18), consistent with these being ABSOLUTE column positions rather than table slot indices.

---

## The Oversized Gap in HENCOTES — Root Cause

The problematic line reads (in the original document):

> *The Place Names of Hexham Region*`[TAB]`, Vic Watts, Master of Grey

The tab sequence is `09 05 01 1c 1c` at offset 0x078E. Target column = `0x1c` = 28 units = **2.8"** from the left margin.

At 10cpi, "The Place Names of Hexham Region" is approximately 34 characters wide = **3.4"**. The cursor is already past the 2.8" tab target, so the renderer advances to the **next** tab stop after 3.4":

| Tab stop grid | Next stop after 3.4" | Gap |
|---------------|----------------------|-----|
| Word default (0.5") | 3.5" | 0.1" — tiny, looks wrong |
| LocoScript default (2.4") | 4.8" | 1.4" — oversized |
| Explicit stop at 2.8" | next stop past 3.4" | depends on stops defined |

The fix is not simply to apply the 2.4" layout-table grid — we need to set an **explicit tab stop at 2.8"** (4032 twips in RTF) for the paragraph so that when the cursor is past 2.8", the renderer can look for the next stop past 3.4" in the correct stop list. Combined with a document-level tab grid matching the layout table (every 2.4" for HENCOTES), subsequent tabs will fall in the right places.

---

## Third ctrl_byte Variant: `0x42` (Memorial.002)

The existing `_detect_ctrl_byte()` function finds the FIRST `22 XX 0b` occurrence in the file and returns `XX`. This works for files using `0x61` or `0x6d` throughout. Memorial.002 breaks this assumption:

| ctrl_byte | Count | Zone |
|-----------|-------|------|
| `0x61` | 39 | Header/pre-body area only |
| `0x42` | 471 | Body content |

The function currently returns `0x61` for Memorial.002, causing the parser to use the wrong ctrl prefix for all body paragraphs. This is a latent bug — Memorial.002 would produce malformed output.

**Fix:** Change `_detect_ctrl_byte()` to return the **most frequent** `XX` value, not the first.

Evidence: scanning `additional info/hexdump_memorial.002`:
- First `22 XX 0b` at 0x05EE → `XX = 0x61` (in pre-body transition zone)
- Body from ~0x0880 onwards uses `22 42 0b` exclusively

---

## Colleague's RTF Converter — Observations

The RTF files in `Additional info/` were produced by a separate tool. Key observations:

- Every paragraph includes `\tqc\tx4513\tqr\tx9026` — hardcoded centre/right tab stops at approximately half-page (3.13") and full-width (6.27") positions. These appear to be defaults applied uniformly, not derived per-file from the layout table or inline tab sequences.
- `0f 04 B1 B2` sequences produce a single `\tab` in the output.
- `09 05 01 XX XX` sequences produce a single `\tab` in the output (confirmed from Hencotes-1.rtf where the problematic line appears with a `\tab` between the italic title and the comma).

This confirms the current approach of emitting `\t` for both sequence types is correct; the gap is in not setting the right stop positions.

---

## Scale Pitch Unit Conversion

At scale pitch `0x18` (24, = 10cpi):

```
1 scale pitch unit = 0.1 inch = 144 twips
```

General formula (scale_pitch byte `P`):
```
characters_per_inch = 240 / P
inch_per_unit       = P / 240
twips_per_unit      = P / 240 × 1440 = P × 6
```

So for `P = 0x18 = 24`: `twips_per_unit = 24 × 6 = 144` ✓

Brewers5 has scale_pitch=`0x14`=20 in the layout entry, consistent with 12cpi (240/20=12):
```
twips_per_unit = 20 × 6 = 120   (1 unit = 0.0833" at 12cpi)
```

---

## Implementation Plan

### 1. Fix `_detect_ctrl_byte()` — return most-frequent, not first

```python
from collections import Counter

def _detect_ctrl_byte(data: bytes) -> int:
    counts = Counter()
    for i in range(len(data) - 2):
        if data[i] == 0x22 and data[i + 2] == 0x0b:
            counts[data[i + 1]] += 1
    return counts.most_common(1)[0][0] if counts else 0x61
```

### 2. Read scale pitch and layout tab stops in `parse()`

```python
# Layout table: 10 × 73-byte entries starting at 0x2C6
_LAYOUT_TABLE_START = 0x2C6
_LAYOUT_ENTRY_SIZE  = 73

scale_pitch = data[_LAYOUT_TABLE_START + 11] if len(data) > _LAYOUT_TABLE_START + 11 else 0x18
twips_per_unit = scale_pitch * 6   # = P × 6

# 15 tab stop absolute positions (scale pitch units), slot 0 is always 0 (unused)
raw_stops = list(data[_LAYOUT_TABLE_START + 33 : _LAYOUT_TABLE_START + 48])
layout_tab_stops_twips = [v * twips_per_unit for v in raw_stops if v > 0]
```

Store in `Document`:
```python
doc.tab_stops: list[int] = []   # in twips
doc.scale_pitch: int = 0x18
```

### 3. Capture per-paragraph tab stop positions

Add to `Paragraph`:
```python
self.tab_stops: list[int] = []   # explicit tab stop positions in twips, collected during parse
```

In the `TAB_SEQ` handler (`09 05 01 XX XX`):
```python
col_twips = data[i + 3] * twips_per_unit   # XX byte × twips_per_unit
current_para.tab_stops.append(col_twips)
current_text.append('\t')
i += 5
```

In the `0f 04` handler:
```python
# After skipping non-printable params, B1 is the first printable byte
b1 = data[j]   # column position
col_twips = b1 * twips_per_unit
current_para.tab_stops.append(col_twips)
# Continue to emit \t as before
```

### 4. RTF output — add `\tx` stops to `\pard`

In `_rtf_para(para)`:
```python
tab_stops = ''
for twips in sorted(set(para.tab_stops)):
    tab_stops += rf'\tx{twips}'
return r'\pard' + align + tab_stops + ' ' + ...
```

If `para.tab_stops` is empty, fall back to document-level stops from the layout table (if we choose to store and use them globally).

### 5. DOCX output — add tab stops to paragraph format

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def _add_tab_stops(paragraph, tab_stops_twips):
    pPr = paragraph._p.get_or_add_pPr()
    tabs = OxmlElement('w:tabs')
    for twips in sorted(set(tab_stops_twips)):
        tab = OxmlElement('w:tab')
        tab.set(qn('w:val'), 'left')
        tab.set(qn('w:pos'), str(twips))
        tabs.append(tab)
    pPr.append(tabs)
```

---

## Files to Change

| File | Change |
|------|--------|
| `parser.py` | Fix `_detect_ctrl_byte()` (most-frequent); add `scale_pitch` + `tab_stops` to `Document`; add `tab_stops` to `Paragraph`; capture column from `09 05 01 XX XX`; capture B1 from `0f 04` handler |
| `converter.py` | RTF: emit `\tx{twips}` in `_rtf_para()`; DOCX: call `_add_tab_stops()` in `_add_para()` |
| `tests/test_parser.py` | New pattern tests for tab stop extraction; fix `_detect_ctrl_byte` most-frequent test |
| `Requirements.md` | Update Binary Format Reference: `09 05 01` and `0f 04` param byte meanings; third ctrl_byte variant `0x42`; scale pitch conversion formula |
| `Tasks.md` | Mark task complete when done |

---

## Open Questions / Risks

1. **Default tab stop fallback**: if a paragraph has no inline tab sequences (plain `\t` from a `09 05 01` with `XX = 0`), should we fall back to the document-level layout tab stop grid? Probably yes, but needs testing.

2. **Multiple `0f 04` sequences per paragraph**: A4Letter has 4 in a row (`0x27 0x2c 0x31 0x4f`). Each emits `\t` and records a tab stop. RTF should emit `\tx3900\tx4400\tx4900\tx7900` (in scaled twips). DOCX similarly. This should produce correct alignment in a multi-column letter layout.

3. **Brewers5 scale pitch**: Layout table shows `0x14` = 20 (12cpi). B1=0x23=35 → 35 × 120 twips = 4200 twips = ~2.9". Needs visual verification against the Brewers5.rtf output after implementation.

4. **Memorial.002 ctrl_byte bug**: the most-frequent fix will return `0x42`, not `0x61`. This is a behaviour change for Memorial — output will likely change significantly (currently broken, hopefully fixed). Needs a new golden fixture or test file.

5. **Zero slot in layout table**: slot 0 is always `0x00`. It is excluded from `raw_stops` via `if v > 0`. Worth confirming this is correct for all sample files.
