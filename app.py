"""
Locoscript 2 Converter — desktop UI (tkinter)
"""
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from converter import SUPPORTED_FORMATS, convert, log_error, log_warning
from parser import ParseError, parse

LOG_FILENAME = 'DocConvertor-Error.log'
OUTPUT_FORMATS = ['.txt', '.rtf', '.docx']


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Locoscript 2 Converter')
        self.resizable(False, False)
        self._files: list[Path] = []
        self._overwrite_policy: str | None = None  # 'yes_all' | 'skip_all' | None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = dict(padx=10, pady=6)

        # --- File selection ---
        file_frame = ttk.LabelFrame(self, text='Input files')
        file_frame.grid(row=0, column=0, columnspan=2, sticky='ew', **pad)

        self._file_listbox = tk.Listbox(file_frame, width=60, height=8, selectmode=tk.EXTENDED)
        self._file_listbox.pack(side='left', fill='both', expand=True, padx=(6, 0), pady=6)

        sb = ttk.Scrollbar(file_frame, orient='vertical', command=self._file_listbox.yview)
        sb.pack(side='left', fill='y', padx=(0, 6), pady=6)
        self._file_listbox.configure(yscrollcommand=sb.set)

        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(side='left', fill='y', padx=6, pady=6)
        ttk.Button(btn_frame, text='Add files…', command=self._add_files).pack(fill='x', pady=2)
        ttk.Button(btn_frame, text='Remove selected', command=self._remove_selected).pack(fill='x', pady=2)
        ttk.Button(btn_frame, text='Clear all', command=self._clear_files).pack(fill='x', pady=2)

        # --- Output format ---
        fmt_frame = ttk.LabelFrame(self, text='Output format')
        fmt_frame.grid(row=1, column=0, sticky='ew', **pad)

        self._fmt_var = tk.StringVar(value='.txt')
        for fmt in OUTPUT_FORMATS:
            ttk.Radiobutton(
                fmt_frame, text=fmt.lstrip('.').upper(),
                variable=self._fmt_var, value=fmt
            ).pack(side='left', padx=10, pady=6)

        # --- Convert button ---
        self._convert_btn = ttk.Button(self, text='Convert', command=self._start_conversion)
        self._convert_btn.grid(row=1, column=1, sticky='ew', **pad)

        # --- Progress / status ---
        self._progress = ttk.Progressbar(self, orient='horizontal', mode='determinate')
        self._progress.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 4))

        self._status_var = tk.StringVar(value='Ready.')
        ttk.Label(self, textvariable=self._status_var, anchor='w').grid(
            row=3, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10)
        )

        self.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # File list management
    # ------------------------------------------------------------------

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title='Select Locoscript 2 files',
            filetypes=[('All files', '*')]
        )
        for p in paths:
            path = Path(p)
            if path not in self._files:
                self._files.append(path)
                self._file_listbox.insert(tk.END, path.name)

    def _remove_selected(self):
        for idx in reversed(self._file_listbox.curselection()):
            self._file_listbox.delete(idx)
            del self._files[idx]

    def _clear_files(self):
        self._file_listbox.delete(0, tk.END)
        self._files.clear()

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _start_conversion(self):
        if not self._files:
            messagebox.showwarning('No files', 'Please add at least one file to convert.')
            return
        self._convert_btn.config(state='disabled')
        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        fmt = self._fmt_var.get()
        total = len(self._files)
        failed = 0
        skipped = 0
        warned = 0
        self._overwrite_policy = None
        start_time = time.monotonic()
        log_path = Path(__file__).parent / LOG_FILENAME

        self._progress.config(maximum=total, value=0)
        self._set_status(f'Converting 0 of {total}…')

        for i, src in enumerate(self._files, start=1):
            self._set_status(f'Converting {i} of {total}: {src.name}')
            dest = src.parent / (src.name + fmt)

            # Overwrite prompt (run on main thread to avoid tkinter issues)
            if dest.exists():
                overwrite = self._ask_overwrite(dest, batch=total > 1)
                if not overwrite:
                    skipped += 1
                    self._step_progress(i)
                    continue

            try:
                with open(src, 'rb') as f:
                    data = f.read()
                doc = parse(data)
                convert(doc, dest)
                output_size = dest.stat().st_size
                if len(data) > 0 and output_size < len(data) * 0.1:
                    warned += 1
                    log_warning(
                        log_path, src.name,
                        f'Output is suspiciously small ({output_size} bytes vs {len(data)} bytes input)'
                        ' — possible parse failure'
                    )
            except Exception as e:
                failed += 1
                log_error(log_path, src.name, e)

            self._step_progress(i)

        elapsed = time.monotonic() - start_time
        self._finish(total, failed, skipped, warned, elapsed)

    def _ask_overwrite(self, dest: Path, batch: bool = False) -> bool:
        """Ask the user whether to overwrite an existing file (called from worker thread).

        In batch mode, also offers 'Yes to All' and 'Skip All' options which set
        _overwrite_policy so subsequent conflicts are resolved without prompting.
        """
        if self._overwrite_policy == 'yes_all':
            return True
        if self._overwrite_policy == 'skip_all':
            return False

        result = [False]
        event = threading.Event()

        def _ask():
            dlg = tk.Toplevel(self)
            dlg.title('File exists')
            dlg.resizable(False, False)
            dlg.grab_set()

            ttk.Label(
                dlg,
                text=f'{dest.name} already exists.\nOverwrite?',
                padding=(12, 12, 12, 6)
            ).pack()

            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(pady=(0, 12), padx=12)

            def choose(value: str):
                result[0] = value in ('yes', 'yes_all')
                if value in ('yes_all', 'skip_all'):
                    self._overwrite_policy = value
                dlg.destroy()
                event.set()

            ttk.Button(btn_frame, text='Yes',  command=lambda: choose('yes')).pack(side='left', padx=4)
            ttk.Button(btn_frame, text='No',   command=lambda: choose('no')).pack(side='left', padx=4)
            if batch:
                ttk.Button(btn_frame, text='Yes to All', command=lambda: choose('yes_all')).pack(side='left', padx=4)
                ttk.Button(btn_frame, text='Skip All',   command=lambda: choose('skip_all')).pack(side='left', padx=4)

            dlg.protocol('WM_DELETE_WINDOW', lambda: choose('no'))

        self.after(0, _ask)
        event.wait()
        return result[0]

    def _step_progress(self, value: int):
        self.after(0, lambda: self._progress.config(value=value))

    def _set_status(self, msg: str):
        self.after(0, lambda: self._status_var.set(msg))

    def _finish(self, total: int, failed: int, skipped: int = 0, warned: int = 0, elapsed: float = 0.0):
        self._convert_btn.config(state='normal')
        succeeded = total - failed - skipped
        skip_note = f', {skipped} skipped' if skipped else ''
        time_note = f'  Time taken: {elapsed:.1f}s'
        warn_note = (
            f'\n{warned} file(s) produced suspiciously small output — possible parse failure.'
            f'\nSee {LOG_FILENAME} for details.'
        ) if warned else ''
        if failed == 0 and warned == 0:
            self.after(0, lambda: messagebox.showinfo(
                'Done',
                f'{succeeded} file(s) converted successfully{skip_note}.{time_note}'
            ))
            self._set_status(f'Done. {succeeded} converted{skip_note}. ({elapsed:.1f}s)')
        elif failed == 0:
            self.after(0, lambda: messagebox.showwarning(
                'Completed with warnings',
                f'{succeeded} file(s) converted{skip_note}.{warn_note}{time_note}'
            ))
            self._set_status(f'Done. {succeeded} converted{skip_note}, {warned} warning(s). ({elapsed:.1f}s)')
        else:
            self.after(0, lambda: messagebox.showwarning(
                'Completed with errors',
                f'{succeeded} file(s) converted{skip_note}.\n'
                f'{failed} file(s) failed — see {LOG_FILENAME} for details.'
                f'{warn_note}{time_note}'
            ))
            self._set_status(f'Done. {succeeded} succeeded{skip_note}, {failed} failed, {warned} warning(s). ({elapsed:.1f}s)')


if __name__ == '__main__':
    App().mainloop()
