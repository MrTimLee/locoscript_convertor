"""
Locoscript 2 file parser.
Handles binary format decoding and text/formatting extraction.
"""

MAGIC = b'DOC'

CTRL_PREFIX    = bytes([0x22, 0x61])        # "a — control sequence prefix
WORD_SEP       = 0x02                        # inter-word space
TAB_SEQ        = bytes([0x09, 0x05, 0x01])  # tab / citation indent
PARA_INDENT    = bytes([0x08, 0x05, 0x01])  # paragraph indent marker (5 bytes total)
SECTION_BREAK  = 0x0e                        # section / page break marker byte
SECTION_BREAK_TYPES = (0x01, 0x02)          # valid second bytes: 0e 01 and 0e 02

# The start of a paragraph content block — used to skip section-break binary data
PARA_CTRL = bytes([0x22, 0x61, 0x0b])

# Inline formatting: second byte of 08 XX (on) / 09 XX (off) sequences.
# The 5-byte 08 05 01 XX XX and 09 05 01 XX XX forms are handled by the PARA_INDENT /
# TAB_SEQ handlers (which also toggle italic ON/OFF).  Bare 08 05 / 09 05 (no 01 suffix)
# fall through to here via _FMT_TYPES[0x05].
_FMT_TYPES = {0x00: 'bold', 0x02: 'underline', 0x05: 'italic', 0x06: 'superscript', 0x07: 'subscript'}

# Header section-header block: always structural, never body text.
# Its presence within 300 bytes of the first PARA_CTRL means we are still
# in the header transition zone — jump past it to find the real content start.
_C40E_BLOCK = bytes([0x22, 0x61, 0x0b, 0xc4, 0x0e])

# ENQ extended character encoding: 05 base 01 diacritic 01
# Maps (base_byte, diacritic_byte) → Unicode character.
# Only combinations confirmed in real sample files are listed.
_ENQ_CHAR_MAP: dict[tuple[int, int], str] = {
    (0x63, 0x13): 'ç',   # c + cedilla  (e.g. "façade", "Français")
}

# High-byte character mappings (0x80–0xFF).
# Built empirically from real LocoScript 2 file evidence only — the Amstrad
# CP/M Plus Wikipedia table is NOT correct for LocoScript 2 (e.g. Wikipedia
# maps 0xE9 → û but real files confirm 0xE9 → £).
_HIGH_BYTE_MAP: dict[int, str] = {
    0x84: '\u2019',  # '  right single quotation mark  (e.g. "Kelly's")
    0x8F: 'æ',       # ae ligature                     (e.g. "Archæology")
    0xB4: 'é',       # e acute                         (e.g. "Café", "née")
    0xC3: 'è',       # e grave                         (e.g. "dix-huitième", "Adèle")
    0xE4: 'ê',       # e circumflex                    (e.g. "Fête")
    0xE8: 'ô',       # o circumflex                    (e.g. "Dépôt")
    0xE9: '£',       # pound sign                      (confirmed; diverges from Amstrad table)
    0xFA: 'ç',       # c cedilla                       (e.g. "façade" — second encoding)
}


class ParseError(Exception):
    pass


class TextRun:
    """A run of plain text with optional inline formatting."""
    def __init__(self, text: str, italic: bool = False, bold: bool = False,
                 underline: bool = False, superscript: bool = False, subscript: bool = False,
                 font_size: float | None = None, page_number: bool = False):
        self.text = text
        self.italic = italic
        self.bold = bold
        self.underline = underline
        self.superscript = superscript
        self.subscript = subscript
        self.font_size = font_size  # point size for this run (None = inherit paragraph/doc default)
        self.page_number = page_number  # True = emit a dynamic page number field, not literal text

    def __repr__(self):
        flags = ', '.join(k for k, v in [
            ('italic', self.italic), ('bold', self.bold), ('underline', self.underline),
            ('superscript', self.superscript), ('subscript', self.subscript),
            ('page_number', self.page_number)] if v)
        return f"TextRun({self.text!r}{', ' + flags if flags else ''})"


class Paragraph:
    """A paragraph containing a list of TextRuns."""
    def __init__(self):
        self.runs: list[TextRun] = []
        self.alignment: str = 'left'  # 'left', 'centre', 'right'
        self.tab_stops: list[int] = []   # explicit tab stop positions in twips
        self.left_indent: int = 0        # left indent in twips (0 = none)
        self.font_size: float | None = None  # point size (None = document default)
        self.page_break_before: bool = False  # True when a page/section break precedes this paragraph

    def plain_text(self) -> str:
        return ''.join('[PAGE]' if r.page_number else r.text for r in self.runs)

    def __repr__(self):
        return f"Paragraph({self.runs!r})"


class Document:
    """Parsed Locoscript 2 document."""
    def __init__(self):
        self.paragraphs: list[Paragraph] = []
        self.header: Paragraph | None = None
        self.footer: Paragraph | None = None

    def plain_text(self) -> str:
        return '\n\n'.join(p.plain_text() for p in self.paragraphs if p.plain_text().strip())


def _detect_variant(data: bytes) -> tuple[int, int]:
    """Return ``(prefix_byte, ctrl_byte)`` for this file.

    Scans for ``PP XX 0b`` sequences where PP is a known prefix byte
    (``0x22`` for standard files, ``0x1e`` for the rarer RS-prefix variant)
    and counts ``(PP, XX)`` pairs.  The most-frequent pair wins.

    Known variants:

    * ``(0x22, 0x61)`` — standard ``DOC`` files (``"a``)
    * ``(0x22, 0x6d)`` — second variant (``"m``, e.g. ``BUILDNGS.A-C``)
    * ``(0x22, 0x42)`` — third variant (``"B``, e.g. ``Memorial.002``)
    * ``(0x1e, 0x74)`` — fourth variant (RS prefix, e.g. ``BINDINDX.HEX``)

    Using the most-frequent pair handles files like ``Memorial.002`` where
    the header zone contains a handful of ``22 61 0b`` blocks before the
    ``22 42 0b`` body content begins.  Returns ``(0x22, 0x61)`` if no
    matching sequence is found.
    """
    from collections import Counter
    counts: Counter = Counter()
    for i in range(len(data) - 2):
        if data[i] in (0x22, 0x1e) and data[i + 2] == 0x0b:
            counts[(data[i], data[i + 1])] += 1
    if not counts:
        return (0x22, 0x61)
    (pb, cb), _ = counts.most_common(1)[0]
    return (pb, cb)


# Layout table: 10 × 73-byte entries starting at 0x2C6.
# Entry offset +11 = scale pitch byte (0x18 = 10cpi = 0.1 inch per unit).
# Entry offset +33..+47 = 15 tab stop absolute positions (scale pitch units).
# Conversion: twips_per_unit = scale_pitch_byte × 6  (e.g. 0x18 × 6 = 144).
_LAYOUT_TABLE_START = 0x2C6
_LAYOUT_ENTRY_SIZE  = 73

# The layout section always starts at 0x5A0 (right after the 10 × 73-byte
# layout table that begins at 0x2C6).  The byte at offset +5 from the
# [0x60–0x9F] 0x00 anchor encodes the type of the FIRST content section.
_LAYOUT_SECTION_START = 0x5A0


def _section_type_at(data: bytes, pos: int, window: int = 80) -> str:
    """Return the section type ('header', 'footer', or 'body') for the section
    whose layout block starts at or shortly after *pos*.

    Scans up to *window* bytes forward for a [0x60–0x9F] 0x00 anchor byte.
    The byte at anchor + 5 encodes the section type:
      0x00 → 'header'
      0x01 → 'footer'
      anything else → 'body'
    Returns 'body' if no anchor is found.
    """
    end = min(pos + window, len(data) - 1)
    for i in range(pos, end):
        if 0x60 <= data[i] <= 0x9F and data[i + 1] == 0x00:
            if i + 5 < len(data):
                marker = data[i + 5]
                if marker == 0x00:
                    return 'header'
                if marker == 0x01:
                    return 'footer'
            return 'body'
    return 'body'


def _find_content_start(data: bytes, ctrl_byte: int = 0x61,
                        prefix_byte: int = 0x22) -> int:
    """
    Find the byte offset where document content begins.

    The first ``PP XX 0b`` is always in the header/transition zone.  If a
    ``PP XX 0b c4 0e`` structural section-header block appears within 300 bytes
    of the current position we are still inside the header — jump past the
    following section break (``0e 01`` / ``0e 02``) to the next ``PP XX 0b``.
    Repeat up to 5 times to handle documents with multiple header cycles.
    """
    para_ctrl = bytes([prefix_byte, ctrl_byte, 0x0b])
    c40e_block = bytes([prefix_byte, ctrl_byte, 0x0b, 0xc4, 0x0e])

    try:
        pos = data.index(para_ctrl)
    except ValueError:
        return 3

    for _ in range(5):
        search_end = min(pos + 300, len(data))
        c4_pos = data.find(c40e_block, pos + 3, search_end)
        if c4_pos == -1:
            break
        # Look for a section/page break byte shortly after the c4 0e block
        sec_pos = None
        for j in range(c4_pos + 5, min(c4_pos + 30, len(data) - 1)):
            if data[j] == 0x0e and data[j + 1] in SECTION_BREAK_TYPES:
                sec_pos = j
                break
        next_para = data.find(para_ctrl, sec_pos + 2 if sec_pos else c4_pos + 5)
        if next_para < 0:
            break
        pos = next_para

    return pos


def _find_body_start(data: bytes, ctrl_byte: int, first_para: int,
                     initial_section: str, prefix_byte: int = 0x22) -> int:
    """Return the byte offset where body content begins.

    For body-only documents (``initial_section == 'body'``) this is
    ``first_para``.  For documents with header/footer pre-body sections,
    ``_find_content_start`` is tried first (reliable when a ``c4 0e``
    structural block is present near the file start).  If it returns
    ``first_para`` (i.e. did not advance), fall back to scanning forward for
    the first ``22 XX 0b`` block satisfying all of:

    - B3 ≠ ``0x00`` (not a layout/transition block)
    - If a high-B3 (≥ ``0x80``) block has been seen earlier in the scan, accept
      the first low-B3 non-zero block unconditionally (we have crossed out of
      the transition zone).  Otherwise apply B5 ≠ ``0x14`` (pre-body paragraphs
      in standard ``22 61`` files carry B5 = ``0x14``; the first body paragraph
      does not).
    - NOT (B3 ≥ ``0x80`` AND B4 == ``0x0e``) (not a structural section block)
    """
    if initial_section == 'body':
        return first_para

    para_ctrl = bytes([prefix_byte, ctrl_byte, 0x0b])
    n = len(data)

    candidate = _find_content_start(data, ctrl_byte, prefix_byte)
    if candidate != first_para:
        return candidate

    # Fallback scan: iterate 22 XX 0b blocks forward from first_para.
    #
    # Two classes of pre-body block appear in practice:
    #
    # A) High-B3 blocks (B3 ≥ 0x80): structural / layout / section-header
    #    metadata — always pre-body.  Seeing one sets a flag that signals we
    #    have entered the transition zone.
    #
    # B) Low-B3 blocks (B3 < 0x80, B3 ≠ 0x00): either pre-body content
    #    (header / footer paragraphs) or the first body paragraph.
    #    Discrimination rule:
    #      - If a high-B3 block has already been seen → this is the body start
    #        (we have crossed out of the transition zone).
    #      - Otherwise → apply the B5 ≠ 0x14 heuristic (pre-body paragraphs
    #        in standard 22-61 files carry B5 = 0x14; the first body paragraph
    #        does not).
    pos = first_para
    seen_high_b3 = False
    while True:
        if pos + 5 < n:
            b3 = data[pos + 3]
            b5 = data[pos + 5]
            if b3 >= 0x80:
                seen_high_b3 = True
            elif b3 != 0x00:
                if seen_high_b3 or b5 != 0x14:
                    return pos
        next_pos = data.find(para_ctrl, pos + 3)
        if next_pos < 0:
            break
        pos = next_pos

    return first_para


def _find_footer_start(data: bytes, ctrl_byte: int, first_para: int,
                       body_start: int, prefix_byte: int = 0x22) -> int:
    """Return the byte offset of the first footer paragraph content block.

    Only meaningful when ``initial_section == 'header'`` (header + footer
    case).  Scans from ``first_para`` to ``body_start`` for a section break
    (``0e 01`` / ``0e 02``); the first ``22 XX 0b`` after that break (and
    before ``body_start``) is ``footer_start``.  Returns ``0`` if not found.
    """
    para_ctrl = bytes([prefix_byte, ctrl_byte, 0x0b])
    n = len(data)

    for j in range(first_para, min(body_start, n - 1)):
        if data[j] == SECTION_BREAK and data[j + 1] in SECTION_BREAK_TYPES:
            nxt = data.find(para_ctrl, j + 2)
            if 0 < nxt < body_start:
                return nxt
            break
    return 0


def _skip_ctrl_sequence(data: bytes, i: int, ctrl_byte: int = 0x61,
                        prefix_byte: int = 0x22) -> int:
    """
    Skip a ``PP XX`` control sequence and return the new offset.

    Type 0x0b (paragraph content) has a fixed 8-byte structure:
        PP XX 0b | 3 param bytes | 2 indent bytes
    All other types: skip prefix + type + 1 byte, then skip any trailing
    non-printable bytes and doubled-pair indent markers.
    """
    para_ctrl = bytes([prefix_byte, ctrl_byte, 0x0b])
    min_dp = 0x20 if prefix_byte == 0x22 else 0x00
    n = len(data)
    ctrl_type = data[i+2] if i+2 < n else 0x00

    if ctrl_type == 0x0b:
        # Structure: 22 XX 0b + 3 param bytes + 2 indent bytes = 8 bytes.
        # Several special cases based on what the param/indent bytes contain:
        if i + 6 < n and data[i+5] == 0x13 and data[i+6] == 0x04:
            # 13 04 formatting prefix starts at B5 — leave it for the main loop
            # to handle as italic-on, italic-off/line-break, or paragraph break.
            i += 5
        elif i + 7 < n and data[i+6] == 0x13 and data[i+7] == 0x04:
            # Indent bytes are 13 04 (a formatting prefix) — leave them for
            # the main loop to handle as italic-on/line-break.
            i += 6
        elif i + 9 < n and data[i+6] == 0x0f and data[i+7] == 0x04:
            # B6/B7 = 0f 04: column spec shifted one byte later than the B5/B6 case,
            # due to an extra B5 sequence byte (e.g. 0x31/0x32/0x33 in BINDINDX.HEX).
            # Structure: PP XX 0b B3 B4 B5 0f 04 B1 B2 [01 XX XX] → content.
            # Consume entirely — no tab emitted — mirroring the B5=0x0f/B6=0x04 case.
            i += 10
            if i < n and data[i] == 0x01:
                i += 1
                if i + 1 < n and data[i] == data[i + 1]:
                    i += 2
        elif (i + 10 < n and data[i+6] == 0x78 and data[i+7] == 0x00 and data[i+8] in (0x01, 0x0a)
              and data[i+9] == data[i+10] and data[i+9] >= 0x20
              and not (data[i+3] >= 0x80 and data[i+4] == 0x0e)):
            # Extended variant: indent area is 78 00, followed by a separator
            # byte (0x01 normally, 0x0a in some 22 6d files) + a real doubled-pair
            # indent marker (B9 == B10, both ≥ 0x20).  Structural header blocks
            # (B3 ≥ 0x80, B4 = 0x0e) are excluded.
            i += 11
        elif (i + 4 < n and prefix_byte == 0x22
              and data[i+3] >= 0x80 and data[i+4] == 0x0e):
            # Any 0b block with a high B3 byte (≥0x80) and 0x0e at B4 is a
            # structural section/layout header with no body text (e.g. c4 0e
            # in standard files, a6 0e / 88 0e / 84 0e in 22 6d variant files).
            # Low-B3 values (e.g. 3a 0e, 36 0e) are normal content blocks and
            # use the default 8-byte skip.  Skip to the next paragraph content
            # block (may be far ahead, past a binary metadata blob).
            # NOTE: this heuristic is 22-prefix only. In 1e files B4=0x0e is
            # a normal top-level entry marker, not a structural indicator.
            next_block = data.find(para_ctrl, i + 5)
            i = next_block if next_block >= 0 else n
        elif (i + 7 < n and prefix_byte == 0x22 and ctrl_byte != 0x61 and data[i+3] < 0x80
              and data[i+6] == 0x78 and data[i+7] == 0x00):
            # 78 00 block without a valid extended-variant doubled pair, in a 22-prefix
            # non-0x61 variant file (22 6d, 22 42, etc.).  These are section-start markers
            # (e.g. "22 6d 0b 42 0d 14 78 00") that carry variable-length structural
            # trailing bytes (separator bytes, column widths, etc.) containing
            # printable values that must not be emitted as text.  Scan forward past
            # the trailing bytes to the next alignment marker (0x11 DC1) or control
            # prefix (PP XX).  Standard 22 61 files never use this trailing structure
            # — their 78 00 blocks use the default 8-byte skip.
            # NOTE: restricted to prefix_byte == 0x22 — in 1e-prefix files B6=0x78
            # B7=0x00 encodes the 12pt font size (B5=0x14 flag), NOT a structural marker.
            # Applying the scan-forward in a 1e file would consume entire paragraphs.
            i += 8
            while i + 1 < n:
                if data[i] == 0x11 or (data[i] == prefix_byte and data[i + 1] == ctrl_byte):
                    break
                i += 1
        elif i + 7 < n and data[i+5] == 0x0a and data[i+6] == 0x09 and data[i+7] == 0x00:
            # Tab-indent variant: 2 param bytes + 0a 09 00 01 + indent pair = 11 bytes.
            i += 11
        elif (prefix_byte != 0x22 and i + 6 < n
              and data[i+5] == 0x11 and data[i+6] == 0x06):
            # Centre-alignment marker at B5/B6 of block header in 1e-prefix variant
            # files.  Skip 5 bytes (the block header up to B4) and leave 11 06 for
            # the main loop to apply the alignment to the current paragraph.
            i += 5
        elif i + 7 < n and data[i+7] == 0x0f:
            # B7 is an 0f SI byte — part of an 0f XX sequence (tab, hanging indent,
            # or Contents Page paragraph separator).  Skip 7 bytes and leave the
            # 0f for the main loop to handle.
            i += 7
        elif i + 8 < n and data[i+7] == 0x13 and data[i+8] == 0x04:
            # 13 04 formatting sequence falls at offset 7-8 (one later than case 1);
            # skip 7 bytes and let the main loop handle the 13 04 xx sequence.
            i += 7
        elif i + 8 < n and data[i+7] == prefix_byte and data[i+8] == ctrl_byte:
            # Another control prefix starts at the indent-byte position;
            # skip 7 bytes and let the main loop handle that control sequence.
            i += 7
        elif i + 8 < n and data[i+5] == 0x0f and data[i+6] == 0x04:
            # SI tab indicator embedded in paragraph header (B5=0x0f B6=0x04):
            # structure is 22 XX 0b B3 B4 0f 04 B1 B2 [01 PP PP] → content.
            # Skip 9 bytes (header + B3 B4 + 0f 04 + B1 B2), then consume the
            # optional 01-separator and identical-byte indent pair.
            i += 9
            if i < n and data[i] == 0x01:
                i += 1
                if i + 1 < n and data[i] == data[i + 1]:
                    i += 2
        else:
            i += 8
    else:
        # Variable structure: skip prefix + type byte (3 bytes).
        # Special case: type == ctrl_byte (e.g. "22 61 61") is a self-referential
        # sequence that always appears as binary layout/page metadata, never as body
        # text.  Skip directly to the next paragraph content block.
        if ctrl_type == ctrl_byte:
            next_block = data.find(para_ctrl, i + 3)
            i = next_block if next_block >= 0 else n
        else:
            # The spec says "+1 extra parameter byte" but using i += 4 would
            # consume 0x13 before the exclusion logic can protect it — leaving
            # 13 04 xx formatting sequences unrecognised.  Using i += 3 and
            # letting the non-printable loop handle parameter bytes (which
            # already excludes 0x13 and WORD_SEP) is equivalent for all other
            # cases and correctly stops before a formatting sequence.
            i += 3
            # Skip any non-printable parameter bytes (but NOT word separators or
            # 0x13 which may start a 13 04 xx formatting sequence)
            while i < n and data[i] < 0x20 and data[i] != WORD_SEP and data[i] != 0x13:
                i += 1
            # Skip doubled-pair indent markers (e.g. 0x54 0x54, 0x3d 0x3d)
            while i+1 < n and data[i] == data[i+1] and data[i] >= min_dp:
                i += 2

    return i


def parse(data: bytes, _prebody_end: int = 0) -> Document:
    """Parse raw Locoscript 2 file bytes into a Document.

    ``_prebody_end`` is a private parameter used when parsing the pre-body
    zone of a ``1e``-prefix file.  When > 0 it overrides ``body_start`` to
    ``_prebody_end`` so that every block in the slice is routed as
    header/footer content (there is no body in the pre-body zone).
    """
    if data[:3] == b'JOY':
        raise ParseError(
            "JOY format files are not currently supported. "
            "This file uses the Locoscript 2 'JOY' document type, which has a "
            "different binary structure from 'DOC' files and requires a separate parser."
        )
    if data[:3] != MAGIC:
        raise ParseError("Not a valid Locoscript 2 file (missing DOC header)")

    prefix_byte, ctrl_byte = _detect_variant(data)
    ctrl_prefix = bytes([prefix_byte, ctrl_byte])
    para_ctrl = bytes([prefix_byte, ctrl_byte, 0x0b])

    # Scale pitch from layout table entry 0 (offset +11).
    # twips_per_unit = scale_pitch_byte × 6 (e.g. 0x18 × 6 = 144 twips = 0.1").
    _scale_pitch = (data[_LAYOUT_TABLE_START + 11]
                    if len(data) > _LAYOUT_TABLE_START + 11 else 0x18)
    _twips_per_unit = _scale_pitch * 6

    # Doubled-pair threshold: 0x22 files use printable bytes (>= 0x20) as indent
    # markers; 0x1e files use smaller column values (>= 0x00).
    min_dp = 0x20 if prefix_byte == 0x22 else 0x00

    doc = Document()
    n = len(data)

    # Determine what type of section begins at the first content block.
    # The layout section (0x5A0) always follows the 10 × 73-byte layout table
    # and its byte at offset +5 encodes: 0x00 = header, 0x01 = footer, else = body.
    initial_section = _section_type_at(data, _LAYOUT_SECTION_START)
    current_section = initial_section

    # Start from the very first paragraph content marker so that header and
    # footer sections are parsed (not skipped) and routed appropriately.
    try:
        first_para = data.index(para_ctrl)
    except ValueError:
        first_para = 3

    prebody_ctrl_byte = 0  # ctrl byte of the pre-body 22 XX zone in 1e-prefix files
    if _prebody_end > 0:
        # Pre-body zone parse: no body exists in this slice — every block is
        # header/footer content.  Setting body_start = _prebody_end (== n)
        # ensures i >= body_start is never true, so the initial_section
        # routing applies throughout.
        body_start = _prebody_end
        footer_start = (_find_footer_start(data, ctrl_byte, first_para, body_start, prefix_byte)
                        if initial_section == 'header' else 0)
    elif prefix_byte != 0x22:
        # 1e-prefix files: every 1e XX 0b block is body content.  The pre-body
        # zone (header/footer sections) uses a separate 22 XX 0b variant and
        # lives before first_para — parse it with a recursive call so that
        # body_start there is forced to len(prebody_data) and all content is
        # correctly routed as header/footer.
        body_start = first_para
        prebody_data = data[:first_para]
        prebody_prefix, prebody_ctrl_byte = _detect_variant(prebody_data)
        if prebody_prefix == 0x22:
            prebody_doc = parse(prebody_data, _prebody_end=len(prebody_data))
            if prebody_doc.header is not None:
                doc.header = prebody_doc.header
            if prebody_doc.footer is not None:
                doc.footer = prebody_doc.footer
        initial_section = 'body'
        current_section = 'body'
        footer_start = 0
    else:
        body_start   = _find_body_start(data, ctrl_byte, first_para, initial_section, prefix_byte)
        footer_start = (_find_footer_start(data, ctrl_byte, first_para, body_start, prefix_byte)
                        if initial_section == 'header' else 0)

    i = first_para

    current_para = Paragraph()
    current_text: list[str] = []
    italic = False
    bold = False
    underline = False
    superscript = False
    subscript = False
    current_font_size: float | None = None

    def flush_run():
        nonlocal current_text
        text = ''.join(current_text)
        if text.strip():
            current_para.runs.append(
                TextRun(text, italic, bold, underline, superscript, subscript, current_font_size)
            )
        current_text = []

    def flush_para():
        nonlocal current_para
        flush_run()
        if not any(r.text.strip() or r.page_number for r in current_para.runs):
            was_page_break = current_para.page_break_before
            current_para = Paragraph()
            current_para.page_break_before = was_page_break
            return
        if current_section == 'header':
            doc.header = current_para
        elif current_section == 'footer':
            doc.footer = current_para
        else:
            doc.paragraphs.append(current_para)
        current_para = Paragraph()

    while i < n:
        # --- Pre-body NUL terminator: 00 00 ---
        # Footer text ends with two consecutive 0x00 bytes before the binary
        # layout blob.  Flush the accumulated footer paragraph and jump forward
        # to the next paragraph content block.  Only active before body_start;
        # safe because the only other 0x00-containing pattern (trailing indent
        # 00 01 XX XX) has a second byte of 0x01, not 0x00.
        # If no content has been accumulated the 00 00 pair is a layout byte
        # that may be followed by text (e.g. "Place: HEXHAM." in MEMORIAL-
        # style documents); skip only the two NUL bytes and keep parsing.
        if i < body_start and data[i] == 0x00 and i + 1 < n and data[i + 1] == 0x00:
            has_content = any(c.strip() for c in current_text) or any(
                r.text.strip() for r in current_para.runs)
            if has_content:
                flush_run()
                flush_para()
                next_para = data.find(para_ctrl, i + 2)
                i = next_para if next_para >= 0 else n
            else:
                i += 2
            continue

        # --- Section / page break: 0e 01 or 0e 02 ---
        # Followed by a binary metadata block; skip ahead to the next paragraph.
        # Peek at the layout block immediately after the break to determine the
        # type of the next section.
        if data[i] == SECTION_BREAK and i+1 < n and data[i+1] in SECTION_BREAK_TYPES:
            flush_run()
            prev = data[i - 1] if i > 0 else 0x00
            mid_sentence = i >= body_start and (prev == 0x02 or 0x20 <= prev <= 0x7e)
            if not mid_sentence:
                flush_para()
                current_para.page_break_before = True
            next_para = data.find(para_ctrl, i + 2)
            i = next_para if next_para >= 0 else n
            continue

        # --- Font size: 13 04 xx  (xx / 10 = point size) ---
        # 0x50=8pt, 0x64=10pt, 0x78=12pt, 0x8c=14pt. Purely inline; no structural meaning.
        if data[i] == 0x13 and i+2 < n and data[i+1] == 0x04:
            flush_run()
            current_font_size = data[i+2] / 10.0
            i += 3
            # Skip trailing: optional 00 null byte, then optional 01 XX XX doubled-pair metadata
            if i < n and data[i] == 0x00:
                i += 1
            if i+2 < n and data[i] == 0x01 and data[i+1] == data[i+2] and data[i+1] > 0:
                i += 3
            continue

        # --- Italic off: 09 05 01 + 2 param bytes ---
        # Consistent with the 09 XX (off) formatting pattern; 0x05 = italic.
        # The two trailing param bytes are consumed to prevent them leaking as artefacts.
        if data[i:i+3] == TAB_SEQ:
            if ''.join(current_text).strip():
                flush_run()
            italic = False
            i += 5  # 09 05 01 + 2 param bytes
            continue

        # --- Italic on: 08 05 01 + 2 byte-count hint bytes ---
        # Consistent with the 08 XX (on) formatting pattern; 0x05 = italic.
        # The two trailing bytes XX XX are a LocoScript screen-layout hint encoding
        # the byte count of the following italic text segment (e.g. XX=0x0a for
        # "Hex. Cour." which is 10 bytes).  They carry no indent semantics and are
        # consumed silently.
        if data[i:i+3] == PARA_INDENT:
            if ''.join(current_text).strip():
                flush_run()
            italic = True
            i += 5  # 08 05 01 + 2 byte-count hint bytes
            continue

        # --- SI tab / hanging-indent sequences: 0f 04 (tab) and 0f 05 (hanging indent) ---
        # Structure: 0f [04|05]
        #            [optional leading non-printable param bytes]
        #            [optional printable tab-stop encoding, up to 2 bytes]
        #            [optional 01 separator + identical-byte indent pair]
        #            → content
        # Without this handler the printable param bytes (e.g. '1a', 'Rf') and any
        # following doubled pairs (e.g. '**', '>>') leak into the output as artefacts.
        # 0f 02 PP ctrl 0b — paragraph break in all file variants.
        # The byte following 0f (01 or 02) distinguishes line-continuation from
        # paragraph-break; checking prefix_byte/ctrl_byte guards against false
        # positives inside binary block headers.
        if (data[i] == 0x0f and i+1 < n and data[i+1] == 0x02
                and i+3 < n and data[i+2] == prefix_byte and data[i+3] == ctrl_byte):
            flush_run()
            flush_para()
            i += 2
            continue

        # 0f 01 PP ctrl 0b — soft screen line-wrap within a paragraph (all variants).
        # LocoScript records where text wrapped on its fixed-width screen, but this
        # carries no semantic meaning in the output — text flows continuously.
        # Emit nothing; let the output renderer wrap at its own margins.
        if (data[i] == 0x0f and i+1 < n and data[i+1] == 0x01
                and i+3 < n and data[i+2] == prefix_byte and data[i+3] == ctrl_byte):
            flush_run()
            i += 2
            continue

        if data[i] == 0x0f and i+1 < n and data[i+1] in (0x04, 0x05):
            is_tab = (data[i+1] == 0x04)
            # In 1e-prefix files, 0f 04 appearing before any paragraph content is a
            # structural column spec (e.g. "0f 04 23 74 01 XX XX" in BINDINDX.HEX).
            # Genuine two-column tabs (e.g. "1852\tHexham Township") always have text
            # in current_text already.  Suppress tab emission and tab-stop recording
            # for structural occurrences in 1e files; emit normally in 22-prefix files.
            is_structural = (is_tab and prefix_byte != 0x22
                             and not ''.join(current_text).strip())
            i += 2
            # Skip leading non-printable param bytes (same rule as variable ctrl handler)
            while i < n and data[i] < 0x20 and data[i] != WORD_SEP and data[i] != 0x13:
                i += 1
            # B1 is the first printable byte: the indent/tab column in scale pitch units.
            # Record it as an explicit tab stop (twips) before consuming both B1 and B2.
            if is_tab and not is_structural and i < n and 0x20 <= data[i] <= 0x7E:
                current_para.tab_stops.append(data[i] * _twips_per_unit)
            # Skip up to 2 printable tab-stop encoding bytes (B1 and B2)
            for _ in range(2):
                if i < n and 0x20 <= data[i] <= 0x7E:
                    i += 1
            # If a 0x01 separator follows, skip it plus any identical-byte indent pair
            if i < n and data[i] == 0x01:
                i += 1
                if i+1 < n and data[i] == data[i+1]:
                    i += 2
            if is_tab and not is_structural:
                flush_run()
                current_text.append('\t')
            continue

        # --- Inline formatting: 08 XX (on) / 09 XX (off) ---
        # bold (00), italic (05 bare form), underline (02), superscript (06), subscript (07).
        # The 5-byte 08 05 01 XX XX and 09 05 01 XX XX forms are handled above by
        # PARA_INDENT / TAB_SEQ; bare 08 05 / 09 05 fall through to here.
        # Params: optional non-printable bytes then optional doubled-pair indent.
        if data[i] in (0x08, 0x09) and i+1 < n and data[i+1] in _FMT_TYPES:
            fmt = _FMT_TYPES[data[i+1]]
            turning_on = (data[i] == 0x08)
            # Only flush if there is real content to preserve in its own run.
            # Whitespace-only content (e.g. a pending '\n') must carry forward
            # into the next run rather than being silently dropped by flush_run().
            if ''.join(current_text).strip():
                flush_run()
            if fmt == 'bold':
                bold = turning_on
            elif fmt == 'italic':
                italic = turning_on
            elif fmt == 'underline':
                underline = turning_on
            elif fmt == 'superscript':
                superscript = turning_on
                if turning_on:
                    subscript = False
            elif fmt == 'subscript':
                subscript = turning_on
                if turning_on:
                    superscript = False
            i += 2
            # Skip optional non-printable param bytes.
            # Exclude 0x02 (WORD_SEP), 0x06 (hyphen/space), 0x0f (SI — starts 0f 02
            # paragraph separators and 0f 04/05 tab sequences), and 0x13 (formatting
            # prefix) as these are structural bytes that must be handled by the main loop.
            while i < n and data[i] < 0x20 and data[i] not in (WORD_SEP, 0x06, 0x0f, 0x13):
                i += 1
            # Skip optional doubled-pair indent marker
            if i+1 < n and data[i] == data[i+1] and data[i] >= min_dp:
                i += 2
            continue

        # --- Doubled prefix byte: PP PP ... (1e-prefix variant self-referential) ---
        # In 1e 74 files the self-referential metadata sequence is 1e 1e 74 01 …
        # rather than 1e 74 74.  The first 1e does not form a valid ctrl_prefix
        # (1e 1e ≠ 1e 74), so it falls through — but then 1e 74 01 is processed
        # as a non-0b control sequence that leaves a printable artefact byte.
        # Detect two consecutive prefix bytes and skip the whole block directly.
        if (prefix_byte != 0x22
                and data[i] == prefix_byte and i+1 < n and data[i+1] == prefix_byte):
            next_block = data.find(para_ctrl, i + 2)
            i = next_block if next_block >= 0 else n
            continue

        # --- Secondary self-referential: 22 prebody_ctrl prebody_ctrl in 1e-prefix body ---
        # Binary page-layout blobs embedded in 1e-prefix body paragraphs contain the
        # 22 XX XX self-referential sequence from the pre-body zone's 22 XX variant
        # (e.g. 22 6d 6d in BINDINDX.HEX, where 0x22='"', 0x6d='m' are printable and
        # leak as '"mmxd' artefacts).  These sequences are never body text — skip to the
        # next para_ctrl, identical to the 22 XX XX handler for 22-prefix files.
        if (prefix_byte != 0x22
                and prebody_ctrl_byte != 0
                and i + 2 < n
                and data[i] == 0x22
                and data[i+1] == prebody_ctrl_byte
                and data[i+2] == prebody_ctrl_byte):
            next_block = data.find(para_ctrl, i + 3)
            i = next_block if next_block >= 0 else n
            continue

        # --- 07 03 in 1e-prefix body = per-page control block page-break ---
        # Some 1e-prefix blocks store per-page LocoScript settings (e.g. "Last page
        # Header / Footer disabled") and end with 07 03 (BEL + ETX) as a page-break
        # marker, followed by a binary layout blob.  The text before 07 03 is internal
        # metadata, not body content.  Discard accumulated text and jump to next para_ctrl.
        # Restricted to 1e-prefix files: in 22-prefix files 07 03 can legitimately follow
        # body content (e.g. BUILDNGS.H "...Haugh Lane?\x07\x03") and must not be discarded.
        if (prefix_byte != 0x22
                and data[i] == 0x07 and i + 1 < n and data[i + 1] == 0x03):
            current_text.clear()
            flush_para()
            current_para.page_break_before = True
            next_para = data.find(para_ctrl, i + 2)
            i = next_para if next_para >= 0 else n
            continue

        # --- Page number token: 07 06 ---
        # BEL (0x07) followed by ACK (0x06) is the LocoScript 2 current-page-number
        # token, confirmed in the footer zones of HENCOTES and BREWERS.5.
        # The token is followed by a SOH-counted display field: 01 N N [N bytes],
        # where N is the byte count and the N bytes are the on-screen placeholder
        # LocoScript rendered (e.g. 3d 3d 02 06 = '==' + word-sep + space).
        # We emit a page_number TextRun (rendered as \chpgn in RTF, a PAGE field
        # in DOCX, and [PAGE] in TXT) and consume the display bytes.
        if data[i] == 0x07 and i + 1 < n and data[i + 1] == 0x06:
            flush_run()
            current_para.runs.append(TextRun('', font_size=current_font_size, page_number=True))
            i += 2
            if i + 2 < n and data[i] == 0x01 and data[i + 1] == data[i + 2]:
                n_display = data[i + 1]
                i += 3 + n_display
            continue

        # --- Control sequence: PP XX ---
        if data[i:i+2] == ctrl_prefix:
            ctrl_type = data[i+2] if i+2 < n else 0
            if ctrl_type in (WORD_SEP, 0x06):
                # PP XX followed immediately by a word separator is literal text
                # only for 0x22 prefix files (where PP = '"' is printable).
                if prefix_byte == 0x22:
                    current_text.append('"')
                    current_text.append(chr(ctrl_byte))
                i += 2
            else:
                _pending_b4_indent = False
                _pending_large_font = 0.0  # deferred 14.4pt: only for confirmed top-level
                if ctrl_type == 0x0b:
                    # Position-based section routing: update current_section
                    # based on where this paragraph content block sits in the file.
                    if i >= body_start:
                        current_section = 'body'
                        # Font size and sub-entry indent for 1e-prefix files.
                        # B5=0x14 in the block header signals an explicit font size
                        # encoded in B6 (B6 / 10 = point size):
                        #   B6=0x78 → 12pt  (sub-entry / cross-reference font)
                        #   B6=0x90 → 14.4pt (top-level heading font — deferred)
                        # Sub-entry indent for 1e-prefix files.
                        # The sole reliable discriminator between top-level entries
                        # and indented sub-entries is whether an external trailing
                        # 01 XX XX doubled pair follows the block:
                        #   top-level headings:  B5=0x14 B6=0x90/0x78 → after skip,
                        #                        external 01 XX XX trailing pair → skip
                        #                        advances i past it → i ≠ i_after_skip
                        #   sub-entries:         B5=0x01 B6=B7 (pair inside header) →
                        #                        no external pair → i == i_after_skip
                        # We set _pending_b4_indent here and apply the 576-twip indent
                        # below (after _skip_ctrl_sequence) only when i == i_after_skip.
                        # B4 is NOT used as a threshold — it proved unreliable (e.g.
                        # "Beaumont Park" has B4=0x0e but is a genuine sub-entry because
                        # it carries no external trailing pair).
                        # B6=0x90 (14.4pt) is similarly deferred: it is the heading font
                        # and must only be applied when the trailing pair confirms top-level.
                        # B6=0x78 (12pt) and other sizes are applied immediately.
                        if prefix_byte != 0x22 and i + 6 < n:
                            b5 = data[i + 5]
                            b6 = data[i + 6]
                            # Guard: don't apply font/indent from a page-break block
                            # (B5=0x14 AND B8=0x07 signals the B8/B9 page-break form).
                            # Such blocks are jumped over below; setting font_size here
                            # would bleed the value into the next paragraph.
                            _is_pagebreak = (i + 8 < n and b5 == 0x14 and data[i + 8] == 0x07)
                            if b5 == 0x14 and not _is_pagebreak:
                                if b6 == 0x90:
                                    # Defer: 14.4pt heading font only applies to fresh top-level
                                    # paragraphs. If left_indent is already set, we're mid-paragraph
                                    # (e.g. after a mid-sentence 0e 02 page break) — suppress it.
                                    if current_para.left_indent == 0:
                                        _pending_large_font = 14.4
                                elif current_para.left_indent == 0:
                                    # Only set font size on a fresh paragraph. Mid-paragraph
                                    # blocks (left_indent already set) are page-break continuations
                                    # and must not override the paragraph's font.
                                    current_para.font_size = b6 / 10.0
                            if not _is_pagebreak and current_para.left_indent == 0:
                                # Defer: apply only if no external trailing pair (i == i_after_skip)
                                _pending_b4_indent = True
                        # MEMORIAL-style paragraph break: "22 XX 0b e8 05 ..." in
                        # the body signals a paragraph boundary (these documents use
                        # 22 XX 0b pairs rather than 13 04 50 between paragraphs).
                        # B3=0xe8, B4=0x05 is the distinctive first-block signature.
                        if i + 4 < n and data[i + 3] == 0xe8 and data[i + 4] == 0x05:
                            flush_run()
                            flush_para()
                        # Page break indicator: B5=0x07 means a binary page-layout
                        # block follows (seen in MEMORIAL-style documents as
                        # "22 XX 0b B3 B4 07 03 ...").  Jump to the next paragraph
                        # content block, skipping the binary metadata.
                        # Guard: exclude structural section headers in 22-prefix files
                        # (B3 >= 0x80, B4 = 0x0e), which legitimately carry 07 03 as
                        # binary layout data — they are handled by _skip_ctrl_sequence.
                        _is_structural_hdr = (prefix_byte == 0x22 and i + 4 < n
                                              and data[i + 3] >= 0x80 and data[i + 4] == 0x0e)
                        if i + 5 < n and data[i + 5] == 0x07 and not _is_structural_hdr:
                            flush_run()
                            flush_para()
                            current_para.page_break_before = True
                            next_para = data.find(para_ctrl, i + 3)
                            i = next_para if next_para >= 0 else n
                            continue
                        # Alternative page break forms in 1e-prefix files where font-size
                        # bytes or an extra param byte shift the 07 03 marker forward:
                        #   "1e 74 0b cc 10 14 90 00 07 03 ..." — 07 03 at B8/B9
                        #   "1e 74 0b ae 10 02 07 03 00 ..."   — 07 03 at B6/B7
                        if i + 8 < n and data[i + 5] == 0x14 and data[i + 8] == 0x07:
                            flush_run()
                            flush_para()
                            current_para.page_break_before = True
                            next_para = data.find(para_ctrl, i + 3)
                            i = next_para if next_para >= 0 else n
                            continue
                        if i + 7 < n and data[i + 6] == 0x07 and data[i + 7] == 0x03:
                            flush_run()
                            flush_para()
                            current_para.page_break_before = True
                            next_para = data.find(para_ctrl, i + 3)
                            i = next_para if next_para >= 0 else n
                            continue
                        # 0e 01 / 0e 02 embedded at B5/B6 of a 1e-prefix block:
                        #   "1e 74 0b cc 10 0e 02 00 ..." — page-break at end of document.
                        # The binary layout blob that follows (a LocoScript date template
                        # etc.) must not be read as body text.
                        if (i + 6 < n and data[i + 5] == 0x0e
                                and data[i + 6] in (0x01, 0x02)):
                            flush_run()
                            flush_para()
                            current_para.page_break_before = True
                            next_para = data.find(para_ctrl, i + 3)
                            i = next_para if next_para >= 0 else n
                            continue
                    elif footer_start > 0 and i >= footer_start:
                        current_section = 'footer'
                    elif initial_section != 'body':
                        current_section = initial_section
                    # B3=0x00: layout/transition block, no body text. Always applies
                    # in the pre-body zone. In the body zone of 1e-prefix files,
                    # B3=0x00, B4=0x00, B5=0x14 together identify a section-boundary
                    # metadata block (e.g. "1e 74 0b 00 00 14 78 00" followed by a
                    # binary layout blob — not body content). The B5=0x14 guard
                    # prevents legitimate detect anchors (B5=0x00) from being
                    # skipped in synthetic test data where body_start == first_para.
                    if i + 5 < n and data[i + 3] == 0x00 and (
                            i < body_start or
                            (prefix_byte != 0x22 and data[i + 4] == 0x00
                             and data[i + 5] == 0x14)):
                        flush_run()
                        flush_para()
                        next_ctrl = data.find(para_ctrl, i + 3)
                        i = next_ctrl if next_ctrl >= 0 else n
                        continue
                i = _skip_ctrl_sequence(data, i, ctrl_byte, prefix_byte)
                i_after_skip = i
                # Skip trailing indent metadata: 00 01 + doubled pair
                if i+3 < n and data[i] == 0x00 and data[i+1] == 0x01 and data[i+2] == data[i+3] and data[i+2] >= min_dp:
                    i += 4
                # Fallback: 01 XX XX (3-byte) trailing indent (e.g. HENCOTES first body para)
                elif i+2 < n and data[i] == 0x01 and data[i+1] == data[i+2] and data[i+1] >= min_dp:
                    i += 3
                # 13 00 WW WW — 4-byte trailer specific to 1e-prefix section-boundary
                # font-size blocks (those preceded by 0f 00 in the binary stream).
                # 0x13 in body text is ALWAYS followed by 0x04 (as 13 04 xx formatting
                # sequences) — 13 00 is never a body-text sequence, so this check is safe.
                # WW is often 0x78 ('x') which would otherwise be emitted as text.
                elif (prefix_byte != 0x22 and ctrl_type == 0x0b
                      and i + 3 < n and data[i] == 0x13 and data[i+1] == 0x00):
                    i += 4
                # B4 sub-entry indent: apply only when no trailing pair was consumed.
                # Entries with a trailing pair are top-level; entries without are genuine
                # indented cross-references (e.g. "see Cockshaw", "see Fore Street").
                if _pending_b4_indent and i == i_after_skip:
                    current_para.left_indent = 576  # 0.4 inch fallback
                    _pending_large_font = 0.0  # 14.4pt is the heading font; suppress for sub-entries
                if _pending_large_font:
                    current_para.font_size = _pending_large_font
            continue

        # --- Word separator: 02 ---
        if data[i] == WORD_SEP:
            current_text.append(' ')
            i += 1
            continue

        # --- Paragraph alignment: 11 06 (centre) / 10 07 or 10 04 (right) ---
        # DC1 + ACK = centre; DLE + BEL/EOT = right.
        # Appear immediately after paragraph content blocks; apply to the
        # current paragraph.  The parameter byte is consumed as part of the
        # 2-byte sequence so it does not emit a spurious space via the 0x06 handler.
        if data[i] == 0x11 and i+1 < n and data[i+1] == 0x06:
            current_para.alignment = 'centre'
            i += 2
            continue
        if data[i] == 0x10 and i+1 < n and data[i+1] in (0x07, 0x04):
            current_para.alignment = 'right'
            i += 2
            continue

        # --- Hyphen / extra space: 06 ---
        # When 0x06 falls between two text characters it is a hyphen.
        # When adjacent to word separators or non-printable bytes it is spacing.
        if data[i] == 0x06:
            prev_printable = i > 0 and data[i-1] >= 0x20
            prev_sep = i > 0 and data[i-1] in (WORD_SEP, 0x06)
            next_sep = i+1 < n and data[i+1] in (WORD_SEP, 0x06)
            if prev_sep and next_sep:
                current_text.append('-')
            elif prev_sep or next_sep or not prev_printable:
                current_text.append(' ')
            else:
                current_text.append('-')
            i += 1
            continue

        # --- ENQ extended character: 05 base 01 diacritic 01 ---
        # Five-byte sequence encoding an accented or extended character.
        # The base byte is a printable ASCII char; the diacritic byte is a
        # small control code identifying the accent.  Some occurrences are
        # followed by a structural doubled-pair indent marker (01 XX XX)
        # which must also be consumed to prevent printable-pair artefacts.
        if (data[i] == 0x05 and i + 4 < n
                and data[i + 2] == 0x01 and data[i + 4] == 0x01
                and 0x21 <= data[i + 1] <= 0x7E):
            base = data[i + 1]
            diacritic = data[i + 3]
            current_text.append(_ENQ_CHAR_MAP.get((base, diacritic), chr(base)))
            i += 5
            # Consume optional trailing structural doubled-pair: 01 XX XX
            if i + 2 < n and data[i] == 0x01 and data[i + 1] == data[i + 2] and data[i + 1] >= 0x20:
                i += 3
            continue

        # --- High-byte character mappings (0x80–0xFF) ---
        if data[i] >= 0x80:
            current_text.append(_HIGH_BYTE_MAP.get(data[i], '?'))
            i += 1
            continue

        # --- Printable ASCII ---
        if 0x20 <= data[i] <= 0x7E:
            current_text.append(chr(data[i]))
            i += 1
            continue

        # --- Everything else: skip ---
        i += 1

    flush_run()
    flush_para()

    return doc
