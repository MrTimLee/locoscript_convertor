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
    for para in doc.paragraphs:
        text = para.plain_text().strip()
        if text:
            lines.append(text)
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
        elif ord(ch) > 127:
            out.append(f'\\u{ord(ch)}?')
        else:
            out.append(ch)
    return ''.join(out)


def to_rtf(doc: Document) -> str:
    header = (
        r'{\rtf1\ansi\deff0'
        r'{\fonttbl{\f0\froman\fcharset0 Times New Roman;}}'
        r'{\colortbl ;}'
        '\n'
    )
    body_parts = []
    for para in doc.paragraphs:
        text = para.plain_text().strip()
        if not text:
            continue
        para_parts = []
        for run in para.runs:
            escaped = _rtf_escape(run.text.strip())
            if not escaped:
                continue
            if run.italic:
                para_parts.append(rf'\i {escaped}\i0 ')
            else:
                para_parts.append(escaped)
        if para_parts:
            body_parts.append(r'\pard ' + ' '.join(para_parts) + r'\par' + '\n')

    return header + ''.join(body_parts) + '}'


def save_rtf(doc: Document, dest: Path) -> None:
    dest.write_text(to_rtf(doc), encoding='ascii', errors='replace')


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def save_docx(doc: Document, dest: Path) -> None:
    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt
    except ImportError as e:
        raise RuntimeError(
            "python-docx is required for DOCX output. "
            "Install it with: pip install python-docx"
        ) from e

    docx = DocxDocument()

    for para in doc.paragraphs:
        if not para.plain_text().strip():
            continue
        p = docx.add_paragraph()
        for run in para.runs:
            text = run.text.strip()
            if not text:
                continue
            r = p.add_run(text + ' ')
            if run.italic:
                r.italic = True

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
