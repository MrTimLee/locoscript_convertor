"""
Output converters: plain text, RTF, and DOCX.
"""
from __future__ import annotations
import datetime
from pathlib import Path

from parser import Document, TextRun


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------

def to_txt(doc: Document) -> str:
    lines = []
    if doc.header and doc.header.plain_text().strip():
        lines.append(doc.header.plain_text().strip(' \n'))
        lines.append('---')
    for para in doc.paragraphs:
        text = para.plain_text().strip(' \n')
        if text.strip():
            lines.append(text)
    if doc.footer and doc.footer.plain_text().strip():
        lines.append('---')
        lines.append(doc.footer.plain_text().strip(' \n'))
    return '\n\n'.join(lines)


def save_txt(doc: Document, dest: Path) -> None:
    dest.write_text(to_txt(doc), encoding='utf-8')


# ---------------------------------------------------------------------------
# RTF
# ---------------------------------------------------------------------------

def _rtf_escape(text: str) -> str:
    """Escape special RTF characters."""
    out = []
    for ch in text:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '{':
            out.append('\\{')
        elif ch == '}':
            out.append('\\}')
        elif ch == '\t':
            out.append(r'\tab ')
        elif ord(ch) > 127:
            out.append(f'\\u{ord(ch)}?')
        else:
            out.append(ch)
    return ''.join(out)


def _rtf_run(run: 'TextRun') -> str:
    """Wrap a TextRun's escaped text in RTF formatting codes."""
    if not run.text.strip():
        return ''
    escaped = _rtf_escape(run.text)
    pre, post = [], []
    if run.bold:
        pre.append(r'\b');       post.insert(0, r'\b0')
    if run.italic:
        pre.append(r'\i');       post.insert(0, r'\i0')
    if run.underline:
        pre.append(r'\ul');      post.insert(0, r'\ulnone')
    if run.superscript:
        pre.append(r'\super');   post.insert(0, r'\nosupersub')
    elif run.subscript:
        pre.append(r'\sub');     post.insert(0, r'\nosupersub')
    prefix = ' '.join(pre) + ' ' if pre else ''
    suffix = ' ' + ' '.join(post) if post else ''
    return prefix + escaped + suffix


def _rtf_para(para: 'Paragraph') -> str:
    """Render a single Paragraph as an RTF paragraph string (no trailing newline)."""
    _rtf_align = {'centre': r'\qc', 'right': r'\qr', 'left': ''}
    parts = [_rtf_run(run) for run in para.runs]
    parts = [p for p in parts if p]
    if not parts:
        return ''
    align = _rtf_align.get(para.alignment, '')
    tab_stops = ''.join(rf'\tx{twips}' for twips in sorted(set(para.tab_stops)))
    return r'\pard' + align + tab_stops + ' ' + ' '.join(parts) + r'\par'


def to_rtf(doc: Document) -> str:
    rtf_header = (
        r'{\rtf1\ansi\deff0'
        r'\paperw11906\paperh16838'
        r'\margl1440\margr1440\margt1440\margb1440'
        r'{\fonttbl{\f0\froman\fcharset0 Times New Roman;}}'
        r'{\colortbl ;}'
        '\n'
    )

    parts = []

    if doc.header and doc.header.plain_text().strip():
        hdr = _rtf_para(doc.header)
        if hdr:
            parts.append(r'{\header ' + hdr + '}\n')

    if doc.footer and doc.footer.plain_text().strip():
        ftr = _rtf_para(doc.footer)
        if ftr:
            parts.append(r'{\footer ' + ftr + '}\n')

    for para in doc.paragraphs:
        if not para.plain_text().strip():
            continue
        p = _rtf_para(para)
        if p:
            parts.append(p + '\n')

    return rtf_header + ''.join(parts) + '}'


def save_rtf(doc: Document, dest: Path) -> None:
    dest.write_text(to_rtf(doc), encoding='ascii', errors='replace')


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def save_docx(doc: Document, dest: Path) -> None:
    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt, Twips
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        raise RuntimeError(
            "python-docx is required for DOCX output. "
            "Install it with: pip install python-docx"
        ) from e

    docx = DocxDocument()

    _docx_align = {
        'centre': WD_ALIGN_PARAGRAPH.CENTER,
        'right':  WD_ALIGN_PARAGRAPH.RIGHT,
    }

    def _apply_tab_stops(paragraph, tab_stops: list) -> None:
        """Add explicit left tab stops (in twips) to a paragraph's XML."""
        if not tab_stops:
            return
        pPr = paragraph._p.get_or_add_pPr()
        tabs_el = OxmlElement('w:tabs')
        for twips in sorted(set(tab_stops)):
            tab = OxmlElement('w:tab')
            tab.set(qn('w:val'), 'left')
            tab.set(qn('w:pos'), str(twips))
            tabs_el.append(tab)
        pPr.append(tabs_el)

    def _add_para(container, para):
        p = container.add_paragraph()
        if para.alignment in _docx_align:
            p.alignment = _docx_align[para.alignment]
        _apply_tab_stops(p, para.tab_stops)
        for run in para.runs:
            if not run.text.strip():
                continue
            r = p.add_run(run.text)
            if run.bold:         r.bold = True
            if run.italic:       r.italic = True
            if run.underline:    r.underline = True
            if run.superscript:  r.font.superscript = True
            if run.subscript:    r.font.subscript = True

    section = docx.sections[0]

    if doc.header and doc.header.plain_text().strip():
        section.header.is_linked_to_previous = False
        # Clear the default empty paragraph python-docx adds
        for p in section.header.paragraphs:
            p.clear()
        _add_para(section.header, doc.header)

    if doc.footer and doc.footer.plain_text().strip():
        section.footer.is_linked_to_previous = False
        for p in section.footer.paragraphs:
            p.clear()
        _add_para(section.footer, doc.footer)

    for para in doc.paragraphs:
        if not para.plain_text().strip():
            continue
        _add_para(docx, para)

    docx.save(dest)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

SUPPORTED_FORMATS = {
    '.txt':  save_txt,
    '.rtf':  save_rtf,
    '.docx': save_docx,
}


def convert(doc: Document, dest: Path) -> None:
    """Convert a parsed Document to the format implied by dest's extension."""
    ext = dest.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {ext!r}. Choose from {list(SUPPORTED_FORMATS)}")
    SUPPORTED_FORMATS[ext](doc, dest)


def log_error(log_path: Path, filename: str, error: Exception) -> None:
    """Append a timestamped error entry to the error log."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{timestamp} - {filename}: {type(error).__name__}: {error}\n"
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)


def log_warning(log_path: Path, filename: str, message: str) -> None:
    """Append a timestamped warning entry to the error log."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{timestamp} - {filename}: [WARNING] {message}\n"
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
