from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from typing import Any, Callable, Dict, cast

try:
    import ttkbootstrap as ttk
    bootstrap_available = True
except Exception:
    from tkinter import ttk
    bootstrap_available = False

from generator.a2l_generator import generate_a2l
from parsers.elf_parser import parse_elf
from parsers.map_parser import parse_map
from utils.logger import Logger

parse_elf_fn = cast(Callable[[str], Dict[str, Any]], parse_elf)
parse_map_fn = cast(Callable[[str], Any], parse_map)
generate_a2l_fn = cast(Callable[..., None], generate_a2l)


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        frozen_base = getattr(sys, "_MEIPASS", None)
        base_path = Path(frozen_base) if frozen_base else Path(__file__).resolve().parent
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path

HISTORY_PATH = Path.home() / ".a2l_generator_history.json"
ACCESS_OPTIONS = ["Read only (measurement)", "Read and Write (measurement + calibration)"]


class A2LGeneratorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root: tk.Tk = root
        self.root.title("A2L Generator")
        self.root.geometry("1100x800")
        self.root.minsize(760, 520)
        self.root.configure(bg="#f4f5f8")

        theme_name = "morph" if bootstrap_available else "clam"
        self.style: Any = ttk.Style()
        if bootstrap_available:
            self.style.theme_use(theme_name)
        self.style.configure("TLabel", font=("Segoe UI", 10), foreground="#2f3b51", background="#f4f5f8")
        self.style.configure("Header.TLabel", font=("Segoe UI Semibold", 16), foreground="#1f3c88", background="#f4f5f8")
        self.style.configure("CardHeader.TLabel", font=("Segoe UI Semibold", 12), foreground="#1c2534", background="#ffffff")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        self.style.configure("Panel.TFrame", background="#f4f5f8")
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=10)
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=10)
        self.style.configure("TEntry", padding=8)
        self.style.configure("TCombobox", padding=8)
        self.style.configure("Tool.TLabel", font=("Segoe UI", 9), foreground="#5f6c7a", background="#f4f5f8")

        main_frame = ttk.Frame(root, style="Panel.TFrame", padding=(24, 24, 24, 24))
        main_frame.pack(fill="both", expand=True)

        header = ttk.Label(main_frame, text="A2L Generation Dashboard", style="Header.TLabel")
        header.grid(row=0, column=0, columnspan=3, sticky="w")

        subheader = ttk.Label(main_frame, text="Create and export A2L files from ELF and MAP sources with a modern corporate UI.", style="Tool.TLabel")
        subheader.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 20))

        left_panel = ttk.Frame(main_frame, style="Panel.TFrame")
        left_panel.grid(row=2, column=0, sticky="nsew", padx=(0, 12))

        right_panel = ttk.Frame(main_frame, style="Panel.TFrame")
        right_panel.grid(row=2, column=1, columnspan=2, sticky="nsew")

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(2, weight=3)

        self._build_file_section(left_panel)
        self._build_options_section(right_panel)
        self._build_log_section(main_frame)

        self.logger: Logger = Logger(self.log_text)
        self.elf_listbox: Any
        self.map_listbox: Any
        self.output_var: Any
        self.output_entry: Any
        self.open_button: Any

        self.load_history()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        """Persist selected files and output name before closing the GUI."""
        self.save_history()
        self.root.destroy()

    def _build_file_section(self, parent: tk.Misc) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)

        # Three rows: ELF (weight=2), MAP (weight=2), Template (weight=1)
        card.rowconfigure(0, weight=2)
        card.rowconfigure(1, weight=0)
        card.rowconfigure(2, weight=2)
        card.rowconfigure(3, weight=0)
        card.rowconfigure(4, weight=1)
        card.rowconfigure(5, weight=0)
        card.columnconfigure(0, weight=1)

        # --- ELF ---
        ttk.Label(card, text="ELF Files", style="CardHeader.TLabel").grid(row=0, column=0, sticky="nw", pady=(0, 4))
        self.elf_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, bd=0, highlightthickness=1,
                                           relief="solid", bg="#f6f7fb", activestyle="none")
        self.elf_listbox.grid(row=0, column=0, sticky="nsew", pady=(22, 4))

        elf_btn = ttk.Frame(card, style="Card.TFrame")
        elf_btn.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        elf_btn.columnconfigure(0, weight=1)
        elf_btn.columnconfigure(1, weight=1)
        ttk.Button(elf_btn, text="Add ELF", command=self.add_elf, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(elf_btn, text="Remove ELF", command=self.remove_elf, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # --- MAP ---
        ttk.Label(card, text="MAP Files", style="CardHeader.TLabel").grid(row=2, column=0, sticky="nw", pady=(0, 4))
        self.map_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, bd=0, highlightthickness=1,
                                           relief="solid", bg="#f6f7fb", activestyle="none")
        self.map_listbox.grid(row=2, column=0, sticky="nsew", pady=(22, 4))

        map_btn = ttk.Frame(card, style="Card.TFrame")
        map_btn.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        map_btn.columnconfigure(0, weight=1)
        map_btn.columnconfigure(1, weight=1)
        ttk.Button(map_btn, text="Add MAP", command=self.add_map, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(map_btn, text="Remove MAP", command=self.remove_map, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # --- Optional Template ---
        ttk.Label(card, text="Optional A2L Template", style="CardHeader.TLabel").grid(row=4, column=0, sticky="nw", pady=(0, 4))
        self.template_listbox: Any = tk.Listbox(card, height=3, selectmode=tk.SINGLE, bd=0, highlightthickness=1,
                                                relief="solid", bg="#f6f7fb", activestyle="none")
        self.template_listbox.grid(row=4, column=0, sticky="nsew", pady=(22, 4))

        tmpl_btn = ttk.Frame(card, style="Card.TFrame")
        tmpl_btn.grid(row=5, column=0, sticky="ew")
        tmpl_btn.columnconfigure(0, weight=1)
        tmpl_btn.columnconfigure(1, weight=1)
        ttk.Button(tmpl_btn, text="Add Template", command=self.add_template, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(tmpl_btn, text="Remove Template", command=self.remove_template, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))

    def _build_options_section(self, parent: tk.Misc) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(18, 18, 18, 12))
        card.pack(fill="both", expand=True)

        # Action bar is packed first so it keeps its space when the window shrinks
        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(button_frame, text="Generate A2L", command=self.generate_a2l, style="Accent.TButton").pack(fill="x")
        self.open_button: Any = ttk.Button(button_frame, text="Open Folder", command=self.open_folder, state="disabled", style="Secondary.TButton")
        self.open_button.pack(fill="x", pady=(6, 0))

        body = self._make_scrollable(card)

        ttk.Label(body, text="Generation Settings", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(body, text="Variable Access").pack(anchor="w", pady=(4, 4))
        self.access_var: Any = tk.StringVar(value=ACCESS_OPTIONS[0])
        self.access_dropdown: Any = ttk.Combobox(body, textvariable=self.access_var, values=ACCESS_OPTIONS, state="readonly")
        self.access_dropdown.pack(fill="x", pady=(0, 10))

        ttk.Label(body, text="Output A2L File").pack(anchor="w", pady=(4, 4))
        self.output_var: Any = tk.StringVar()
        self.output_entry: Any = ttk.Entry(body, textvariable=self.output_var)
        self.output_entry.pack(fill="x", pady=(0, 14))

        # XCP identifiers are not contained in ELF/MAP, they come from the ECU XCP configuration
        ttk.Label(body, text="XCP CAN Request ID (master, hex)").pack(anchor="w", pady=(4, 4))
        self.xcp_request_var: Any = tk.StringVar()
        ttk.Entry(body, textvariable=self.xcp_request_var).pack(fill="x", pady=(0, 10))

        ttk.Label(body, text="XCP CAN Response ID (slave, hex)").pack(anchor="w", pady=(4, 4))
        self.xcp_response_var: Any = tk.StringVar()
        ttk.Entry(body, textvariable=self.xcp_response_var).pack(fill="x", pady=(0, 14))

        ttk.Label(body, text="Aggregate variables").pack(anchor="w", pady=(4, 4))
        self.expand_all_var: Any = tk.BooleanVar(value=False)
        self.expand_arrays_var: Any = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Extended A2L (expand all structures, unions and arrays)",
                variable=self.expand_all_var,
                command=self._on_expand_all_changed).pack(anchor="w")
        ttk.Checkbutton(body, text="Expand arrays only",
                variable=self.expand_arrays_var,
                command=self._on_expand_arrays_changed).pack(anchor="w", pady=(0, 10))

        self.advanced_var: Any = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Advanced mode (pick variables and access individually)",
                        variable=self.advanced_var).pack(anchor="w", pady=(0, 4))

    def _make_scrollable(self, parent: tk.Misc) -> ttk.Frame:
        """Wrap the settings in a scrollable canvas so nothing is clipped on small windows."""
        canvas = tk.Canvas(parent, bg="#ffffff", highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Card.TFrame")

        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        # Wheel is only captured while the pointer is over the settings card
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def _on_expand_all_changed(self) -> None:
        """Keep expansion choices mutually exclusive."""
        if self.expand_all_var.get():
            self.expand_arrays_var.set(False)

    def _on_expand_arrays_changed(self) -> None:
        """Keep expansion choices mutually exclusive."""
        if self.expand_arrays_var.get():
            self.expand_all_var.set(False)

    def _expansion_mode(self) -> str:
        """Return the selected aggregate expansion mode for ELF parsing."""
        if self.expand_all_var.get():
            return "all"
        if self.expand_arrays_var.get():
            return "arrays"
        return "none"

    def _build_log_section(self, parent: tk.Misc) -> None:
        log_card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        log_card.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(18, 0))
        parent.rowconfigure(3, weight=1)

        ttk.Label(log_card, text="Activity Log", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        self.log_text: scrolledtext.ScrolledText = scrolledtext.ScrolledText(log_card, wrap="word", height=6, bg="#f6f7fb", fg="#2f3b51", relief="flat", bd=0, highlightthickness=1, highlightbackground="#d9dee9")
        self.log_text.pack(fill="both", expand=True)

    def add_elf(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("ELF files", "*.elf")])
        if file_path:
            self.elf_listbox.insert(tk.END, file_path)
            self._set_default_output_name(file_path)
            self.save_history()

    def remove_elf(self) -> None:
        selection = self.elf_listbox.curselection()
        if selection:
            self.elf_listbox.delete(selection[0])
            self.save_history()

    def _set_default_output_name(self, elf_path: str) -> None:
        if not self.output_var.get():
            default_name = os.path.splitext(os.path.basename(elf_path))[0] + ".a2l"
            self.output_var.set(default_name)

    def add_map(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Map files", "*.map")])
        if file_path:
            self.map_listbox.insert(tk.END, file_path)
            self.save_history()

    def remove_map(self) -> None:
        selection = self.map_listbox.curselection()
        if selection:
            self.map_listbox.delete(selection[0])
            self.save_history()

    def load_history(self) -> None:
        if not HISTORY_PATH.exists():
            return
        try:
            with open(HISTORY_PATH, "r") as f:
                history: dict[str, list[str]] = json.load(f)
            for path in history.get("elf_files", []):
                self.elf_listbox.insert(tk.END, path)
            for path in history.get("map_files", []):
                self.map_listbox.insert(tk.END, path)
            for path in history.get("template_files", []):
                self.template_listbox.insert(tk.END, path)
            self.output_var.set(history.get("output_name", ""))
        except Exception:
            pass

    def save_history(self) -> None:
        history: dict[str, list[str]] = {
            "elf_files": [str(item) for item in self.elf_listbox.get(0, tk.END)],
            "map_files": [str(item) for item in self.map_listbox.get(0, tk.END)],
            "template_files": [str(item) for item in self.template_listbox.get(0, tk.END)],
            "output_name": self.output_var.get(),
        }
        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    def generate_a2l(self) -> None:
        try:
            elf_sel = self._get_single_selection(self.elf_listbox)
            map_sel = self._get_single_selection(self.map_listbox)
            if not elf_sel:
                messagebox.showerror("Error", "Please select an ELF file.")
                return

            template_sel = self._get_selected_template()
            advanced_mode = bool(self.advanced_var.get())
            output_name = self.output_var.get() or os.path.splitext(os.path.basename(elf_sel))[0] + ".a2l"
            output_path = os.path.join(os.path.dirname(elf_sel), output_name)
            self.output_var.set(output_name)
            self.save_history()

            self.logger.log(f"Access: {self.access_var.get()}")
            self.logger.log(f"Parsing ELF: {elf_sel}")
            started = time.perf_counter()
            expansion_mode = self._expansion_mode()
            self.logger.log(f"Aggregate expansion: {expansion_mode}")
            elf_symbols = parse_elf_fn(elf_sel, expansion_mode=expansion_mode)
            self.logger.log(f"Found {len(elf_symbols) - 1} data symbols in {time.perf_counter() - started:.1f} s.")

            map_symbols = {}
            if map_sel:
                self.logger.log(f"Parsing MAP: {map_sel}")
                map_symbols = parse_map_fn(map_sel)

            selected_symbols = None
            if advanced_mode:
                selected_symbols = self._show_advanced_variable_selection(elf_symbols)
                if selected_symbols is None:
                    self.logger.log("Generation cancelled by user.")
                    return
                self.logger.log(f"Advanced mode selected; generating {len(selected_symbols)} variables.")

            self.logger.log("Generating A2L...")
            generate_a2l_fn(elf_symbols, map_symbols, output_path, template_sel,
                            selected_symbols, advanced_mode,
                            self._parse_can_id(self.xcp_request_var.get()),
                            self._parse_can_id(self.xcp_response_var.get()),
                            self.access_var.get())

            self.logger.log("Generation successful.")
            self.open_button.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self.logger.log(f"Error: {exc}")

    @staticmethod
    def _parse_can_id(text: str) -> int | None:
        """Parse a CAN identifier as hex, with or without 0x prefix; empty input disables IF_DATA XCP."""
        value = text.strip()
        if not value:
            return None
        try:
            return int(value, 16)
        except ValueError:
            raise ValueError(f"Invalid XCP CAN ID: {text}")

    def _get_single_selection(self, listbox: tk.Listbox) -> str:
        """Return the selected item; fall back to the first item if nothing is selected."""
        sel = listbox.curselection()
        if sel:
            return str(listbox.get(sel[0]))
        if listbox.size() > 0:
            return str(listbox.get(0))
        return ""

    def _get_selected_template(self) -> str | None:
        value = self._get_single_selection(self.template_listbox)
        return value if value else None

    def add_template(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("A2L Template files", "*.a2l;*.txt"), ("All files", "*.*")])
        if file_path:
            self.template_listbox.insert(tk.END, file_path)
            self.save_history()

    def remove_template(self) -> None:
        selection = self.template_listbox.curselection()
        if selection:
            self.template_listbox.delete(selection[0])
            self.save_history()

    def _show_advanced_variable_selection(self, elf_symbols: dict[str, Any]) -> dict[str, str] | None:
        """Pick variables from the ELF data objects and assign read or read/write access."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Variable Selection")
        dialog.geometry("1000x600")
        dialog.minsize(760, 460)
        dialog.transient(self.root)
        dialog.grab_set()

        available = {
            name: info for name, info in elf_symbols.items()
            if name != "_enums" and info.get("size", 0) > 0
        }

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=0)
        dialog.columnconfigure(2, weight=1)
        dialog.rowconfigure(1, weight=1)

        filter_frame = ttk.Frame(dialog, padding=(10, 10, 10, 0))
        filter_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter").grid(row=0, column=0, padx=(0, 8))
        filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=filter_var).grid(row=0, column=1, sticky="ew")
        statics_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Statics only", variable=statics_var).grid(row=0, column=2, padx=(10, 0))

        left_frame = ttk.Frame(dialog, padding=10)
        left_frame.grid(row=1, column=0, sticky="nsew")
        right_frame = ttk.Frame(dialog, padding=10)
        right_frame.grid(row=1, column=2, sticky="nsew")

        ttk.Label(left_frame, text="Available ELF Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        left_listbox: Any = tk.Listbox(left_frame, selectmode=tk.EXTENDED, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        left_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=left_listbox.yview)
        left_listbox.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right", fill="y")
        left_listbox.pack(fill="both", expand=True)

        ttk.Label(right_frame, text="Selected Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        right_listbox: Any = tk.Listbox(right_frame, selectmode=tk.EXTENDED, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        right_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=right_listbox.yview)
        right_listbox.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        right_listbox.pack(fill="both", expand=True)

        chosen: dict[str, str] = {}
        shown: list[str] = []

        def label_for(name: str) -> str:
            info = available[name]
            tag = " [static]" if info.get("static") else ""
            return f'{name}  ({info.get("datatype", "?")} @ 0x{info.get("address", 0):08X}){tag}'

        def refresh_left() -> None:
            needle = filter_var.get().strip().lower()
            statics_only = statics_var.get()
            shown.clear()
            left_listbox.delete(0, tk.END)
            for name in sorted(available):
                if name in chosen:
                    continue
                if statics_only and not available[name].get("static"):
                    continue
                if needle and needle not in name.lower():
                    continue
                shown.append(name)
                left_listbox.insert(tk.END, label_for(name))

        def refresh_right() -> None:
            right_listbox.delete(0, tk.END)
            for name in sorted(chosen):
                right_listbox.insert(tk.END, f'{name}  [{chosen[name].upper()}]')

        def add(access: str, everything: bool = False) -> None:
            names = shown[:] if everything else [shown[i] for i in left_listbox.curselection()]
            for name in names:
                chosen[name] = access
            refresh_left()
            refresh_right()

        def remove(everything: bool = False) -> None:
            names = sorted(chosen) if everything else [sorted(chosen)[i] for i in right_listbox.curselection()]
            for name in names:
                chosen.pop(name, None)
            refresh_left()
            refresh_right()

        control_frame = ttk.Frame(dialog, padding=10)
        control_frame.grid(row=1, column=1, sticky="ns")
        ttk.Button(control_frame, text="Add  >  Read", command=lambda: add("r")).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add  >  Read/Write", command=lambda: add("rw")).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add All  >  Read", command=lambda: add("r", True)).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add All  >  Read/Write", command=lambda: add("rw", True)).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="<  Remove", command=lambda: remove()).pack(fill="x", pady=(16, 3))
        ttk.Button(control_frame, text="<<  Remove All", command=lambda: remove(True)).pack(fill="x", pady=3)

        button_frame = ttk.Frame(dialog, padding=10)
        button_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        result: dict[str, str] | None = {}

        def on_ok() -> None:
            if not chosen:
                messagebox.showwarning("Selection Required", "Please select at least one variable before generating A2L.")
                return
            nonlocal result
            result = dict(chosen)
            dialog.destroy()

        def on_cancel() -> None:
            nonlocal result
            result = None
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok, style="Accent.TButton").pack(side="right", padx=8)
        ttk.Button(button_frame, text="Cancel", command=on_cancel, style="Secondary.TButton").pack(side="right")

        filter_var.trace_add("write", lambda *_a: refresh_left())
        statics_var.trace_add("write", lambda *_a: refresh_left())
        refresh_left()

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.root.wait_window(dialog)
        return result

    def open_folder(self) -> None:
        import subprocess

        elf_sel = self._get_single_selection(self.elf_listbox)
        if elf_sel:
            folder = os.path.dirname(elf_sel)
            subprocess.Popen(f'explorer "{folder}"')

