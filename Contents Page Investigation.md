# Contents Page Control Block — Investigation

## Problem

In `22 6d` variant files (105 of the sample set), the Contents Page is parsed as a single collapsed paragraph instead of one paragraph per entry. Two symptoms:

1. **Spurious `x`** at the start of the Contents paragraph
2. **`'m` separators** between entry names instead of paragraph breaks

Confirmed in `manual_tests/BUILDNGS.A-C` and `manual_tests/BUILDNGS.D-G`. Worst-case example: `PUBSHIST.BAK` has 309 missing separators and collapses to exactly 1 paragraph.

---

## Root Causes

### Bug A — Spurious `x`

At offset `0x6d2` in BUILDNGS.A-C there is a `22 6d 0b 42 0d 14 78 00 0a ...` block. The existing extended-variant skip in `_skip_ctrl_sequence` checks for `B6=0x78, B7=0x00, data[i+8]==0x01`, but here `data[i+8]==0x0a`. The check fails, the default `+8` skip is taken instead, and the parser lands at offset `0x6da`. It then steps through bytes `0a 05 00 13 00` as unknowns until it reaches `0x6df = 0x78 = 'x'`, which is printable and gets emitted as literal text.

**Fix:** Relax the third-byte check — either accept any value for `data[i+8]` in the `78 00` variant, or specifically also accept `0x0a`.

### Bug B — Collapsed Contents Entries

The Contents Page uses `0f 02 22 6d 0b [6 bytes]` as its paragraph separator, not `13 04 50`. The `0f` handler in the parser only fires for second bytes `0x04` (tab) and `0x05` (hanging indent). When `data[i+1] == 0x02`, the `0f` falls through to "everything else: `i+=1`", the `0x02` emits a word-separator space, and the `22 6d 0b` block is processed without flushing the paragraph.

The `'m` artefacts come from the `0f 04 27 6d 01 XX XX` tab-stop bytes that follow each entry — `0x27 0x6d` = `'m` — which should be silently consumed by the `0f 04` handler, but aren't because the handler fires at the wrong offset after the collapsed sequence.

---

## Binary Structure of a Contents Page Section

```
[body_start]
22 6d 0b + 11 06 (centre alignment) + [Contents Page title text]
-- repeated per entry: --
0f 02                                  ← paragraph/entry separator
22 6d 0b [B3 B4 B5 B6] 0f              ← page-position block (8 bytes)
0f 04 27 6d 01 XX XX                   ← left-indent tab stop for this entry
[entry text words separated by 02]     ← entry name
...repeats...
13 04 50                               ← ONE paragraph break at end of entire Contents section
```

The `0f 01 22 6d 0b` variant also appears (475 occurrences in BUILDNGS.A-C) and represents a **line break within a paragraph** (content continues in the same entry).

---

## Pattern Counts (BUILDNGS.A-C)

| Pattern | Count | Meaning |
|---------|-------|---------|
| `0f 02 22 6d 0b` | 568 | Paragraph/entry separator — flush paragraph |
| `0f 01 22 6d 0b` | 479 | Line break within paragraph |
| `0f 04 [params]` | 50 | Tab marker — already handled correctly |
| `0f 05 [params]` | 6 | Hanging indent — already handled correctly |

---

## Body-Safety Analysis

Body text in `22 6d` files also contains `0f 02 22 6d 0b` blocks, but these always appear **after** a `13 04 78` line break, which means no text has been accumulated when `0f 02` is encountered. Since `flush_para()` discards empty paragraphs, treating `0f 02` as a paragraph flush is a safe no-op in the body case.

---

## Scale

105 of the files in `sample_files/` are `22 6d` variant files. All are affected by Bug B. The `22 42` variant (`Memorial.002`) uses different paragraph separators (`22 42 0b e8 05`) and is unaffected.

---

## Implementation Plan

### Fix 1 — Spurious `x` (`_skip_ctrl_sequence`, parser.py ~line 262)

The `78 00 01` extended-variant check:
```python
elif i + 8 < n and data[i+6] == 0x78 and data[i+7] == 0x00 and data[i+8] == 0x01:
    i += 11
```
Change to not require the third byte to be exactly `0x01`:
```python
elif i + 7 < n and data[i+6] == 0x78 and data[i+7] == 0x00:
    i += 11
```
(still skip 11 bytes — the payload structure is the same regardless of the third byte value)

### Fix 2 — Contents entries / `0f 01` and `0f 02` (`parse()` main loop, parser.py ~line 509)

Extend the `0f` handler to detect `0f 01` and `0f 02` when immediately followed by `22 ctrl 0b`:

```python
# 0f 01 22 ctrl 0b — line break, skip 8-byte ctrl block
if data[i+1] == 0x01 and i+2 < n and data[i+2:i+4] == bytes([0x22, ctrl_byte]):
    flush_run()
    current_text.append('\n')
    i += 2  # skip 0f 01, leave 22 ctrl 0b for the ctrl handler
    continue

# 0f 02 22 ctrl 0b — paragraph separator, flush paragraph, skip 8-byte ctrl block
if data[i+1] == 0x02 and i+2 < n and data[i+2:i+4] == bytes([0x22, ctrl_byte]):
    flush_run()
    flush_para()
    i += 2  # skip 0f 02, leave 22 ctrl 0b for the ctrl handler
    continue
```

By only skipping `0f 01`/`0f 02` and leaving the `22 ctrl 0b` for the existing ctrl handler, we avoid duplicating block-skip logic.

### Tests Needed

1. `0f 02 22 6d 0b` in a `22 6d` file produces a paragraph break between entries
2. `0f 01 22 6d 0b` in a `22 6d` file produces a line break within a paragraph
3. `22 6d 0b 42 0d 14 78 00 0a` no longer emits spurious `x`
4. Body `0f 02 22 6d 0b` (after `13 04 78`) does not create a spurious empty paragraph
