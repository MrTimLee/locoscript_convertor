# Locoscript 2 Converter

A desktop application for converting Locoscript 2 documents (Amstrad PCW word processor files) to modern formats: plain text, RTF, or DOCX.

---

## Prerequisites

### Python

The application requires **Python 3.10 or later**.

**Mac**

Check whether Python is already installed:
```
python3 --version
```
If it is not installed, download it from [python.org](https://www.python.org/downloads/) and run the installer. Make sure to tick **"Add Python to PATH"** on the installer's first screen.

**Windows**

Download Python from [python.org](https://www.python.org/downloads/) and run the installer. Make sure to tick **"Add Python to PATH"** on the installer's first screen.

After installation, verify in a Command Prompt or PowerShell window:
```
python --version
```

---

## Installation

### 1. Download the application

Download the project folder and place it somewhere convenient, for example your Desktop or Documents folder.

### 2. Open a terminal in the project folder

**Mac:** Right-click the folder in Finder and choose **New Terminal at Folder**, or open Terminal and type:
```
cd ~/Desktop/locoscript_convertor
```

**Windows:** Open the folder in Explorer, then click the address bar, type `cmd`, and press Enter.

### 3. Create a virtual environment

```
python3 -m venv venv        # Mac
python  -m venv venv        # Windows
```

### 4. Activate the virtual environment

**Mac:**
```
source venv/bin/activate
```

**Windows:**
```
venv\Scripts\activate
```

You should see `(venv)` appear at the start of your prompt.

### 5. Install dependencies

```
pip install -r requirements.txt
```

This installs `python-docx`, the only third-party package required. Plain text and RTF output have no additional dependencies.

---

## Running the application

With the virtual environment active, run:

```
python app.py        # Mac
python app.py        # Windows
```

The converter window will open.

> **Tip:** On Mac you can also double-click `app.py` in Finder if Python is set as the default application for `.py` files — but running from the terminal is more reliable.

---

## Using the application

### Converting individual files

1. **Add files** — Click **Add files…** and select one or more Locoscript 2 documents. These files have no extension.
2. **Choose output format** — Select **TXT**, **RTF**, or **DOCX** using the radio buttons.
3. **Convert** — Click **Convert**. Converted files are saved in the same folder as the originals, with the chosen extension added.

If a converted file already exists you will be asked whether to overwrite it. When converting multiple files you can choose to overwrite or skip all without being asked again for each one.

A summary message is shown when conversion finishes. If any files fail, the error details are written to `DocConvertor-Error.log` in the application folder.

### Shadow Copy mode

Shadow Copy mode converts an entire folder of Locoscript 2 files in one operation, preserving the original folder structure.

1. **Choose output format** — Select **TXT**, **RTF**, or **DOCX** using the radio buttons.
2. **Shadow Copy Directory…** — Click the button and select the source folder.
3. The application scans the folder recursively. Files identified as Locoscript 2 documents (by their `DOC` magic bytes, regardless of file extension) are converted. All other files are skipped and logged as warnings.
4. Converted files are written to a new folder at the same level as the source, named `Converted_<SourceFolderName>` (e.g. source folder `Archive` → output folder `Converted_Archive`). The subfolder hierarchy mirrors the source exactly, and each file keeps its original name with the chosen extension added.
5. If the output folder already exists you will be prompted to confirm before proceeding.

A summary message is shown on completion, including the number of files converted, any failures, and a count of non-Locoscript files that were skipped. Full error details are written to `DocConvertor-Error.log` in the application folder.

---

## Running the tests

With the virtual environment active:
```
python -m unittest tests/test_parser.py -v
```

To regenerate the golden fixture after an intentional parser improvement:
```
python tests/regenerate_golden.py
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `python: command not found` (Mac) | Use `python3` instead of `python` |
| `No module named tkinter` | On Linux only: install with `sudo apt install python3-tk`. Mac and Windows include tkinter with Python. |
| `No module named docx` | Run `pip install -r requirements.txt` with the virtual environment active |
| App window does not appear on Mac | Ensure you are running Python from python.org, not a headless Homebrew build |
| File not recognised as Locoscript 2 | The file must begin with the bytes `DOC`. Check it was copied from the PCW without corruption. |
