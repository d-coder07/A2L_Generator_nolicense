from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from typing import Any, Callable, cast

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

parse_elf_fn = cast(Callable[[str], dict[str, Any]], parse_elf)
parse_map_fn = cast(Callable[[str], Any], parse_map)
generate_a2l_fn = cast(Callable[[dict[str, Any], Any, str], None], generate_a2l)


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        frozen_base = getattr(sys, "_MEIPASS", None)
        base_path = Path(frozen_base) if frozen_base else Path(__file__).resolve().parent
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path

CONFIG_PATH = resource_path("config/compilers.json")
HISTORY_PATH = Path.home() / ".a2l_generator_history.json"
FORMAT_OPTIONS = ["Classic A2L", "Extended A2L", "AUTOSAR A2L"]


class A2LGeneratorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root: tk.Tk = root
        self.root.title("A2L Generator")
        self.root.geometry("1100x800")
        self.root.minsize(1000, 750)
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

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.compilers: list[str] = json.load(f)["compilers"]

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
        main_frame.rowconfigure(2, weight=1)

        self._build_file_section(left_panel)
        self._build_options_section(right_panel)
        self._build_log_section(main_frame)

        self.logger: Logger = Logger(self.log_text)
        self.elf_listbox: Any
        self.map_listbox: Any
        self.compiler_var: Any
        self.format_var: Any
        self.output_var: Any
        self.output_entry: Any
        self.open_button: Any
        self.compiler_dropdown: Any
        self.format_dropdown: Any

    def _build_file_section(self, parent: tk.Misc) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="Source Files", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))

        self.elf_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        self.elf_listbox.pack(fill="both", expand=True, pady=(0, 10))

        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(fill="x", pady=(0, 14))
        ttk.Button(button_frame, text="Add ELF", command=self.add_elf, style="Accent.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(button_frame, text="Remove ELF", command=self.remove_elf, style="Secondary.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.map_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        self.map_listbox.pack(fill="both", expand=True, pady=(0, 10))

        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(fill="x")
        ttk.Button(button_frame, text="Add MAP", command=self.add_map, style="Accent.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(button_frame, text="Remove MAP", command=self.remove_map, style="Secondary.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(6, 0))

        ttk.Label(card, text="Optional A2L Template", style="CardHeader.TLabel").pack(anchor="w", pady=(16, 10))

        self.template_listbox: Any = tk.Listbox(card, height=3, selectmode=tk.SINGLE, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        self.template_listbox.pack(fill="both", expand=True, pady=(0, 10))

        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(fill="x")
        ttk.Button(button_frame, text="Add Template", command=self.add_template, style="Accent.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(button_frame, text="Remove Template", command=self.remove_template, style="Secondary.TButton", width=20).pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _build_options_section(self, parent: tk.Misc) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=False)

        ttk.Label(card, text="Generation Settings", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(card, text="Compiler").pack(anchor="w", pady=(4, 4))
        self.compiler_var: Any = tk.StringVar(value=self.compilers[0] if self.compilers else "")
        self.compiler_dropdown: Any = ttk.Combobox(card, textvariable=self.compiler_var, values=self.compilers, state="readonly")
        self.compiler_dropdown.pack(fill="x", pady=(0, 10))

        ttk.Label(card, text="Output Format").pack(anchor="w", pady=(4, 4))
        self.format_var: Any = tk.StringVar(value=FORMAT_OPTIONS[0])
        self.format_dropdown: Any = ttk.Combobox(card, textvariable=self.format_var, values=FORMAT_OPTIONS, state="readonly")
        self.format_dropdown.pack(fill="x", pady=(0, 10))

        ttk.Label(card, text="Output A2L File").pack(anchor="w", pady=(4, 4))
        self.output_var: Any = tk.StringVar()
        self.output_entry: Any = ttk.Entry(card, textvariable=self.output_var)
        self.output_entry.pack(fill="x", pady=(0, 14))

        self.advanced_var: Any = tk.BooleanVar(value=False)
        ttk.Checkbutton(card, text="Advanced mode", variable=self.advanced_var).pack(anchor="w", pady=(0, 14))

        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(fill="x")
        ttk.Button(button_frame, text="Generate A2L", command=self.generate_a2l, style="Accent.TButton", width=30).pack(fill="x", padx=(0, 0))
        self.open_button: Any = ttk.Button(button_frame, text="Open Folder", command=self.open_folder, state="disabled", style="Secondary.TButton", width=30)
        self.open_button.pack(fill="x", pady=(6, 0))

    def _build_log_section(self, parent: tk.Misc) -> None:
        log_card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        log_card.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(18, 0))
        parent.rowconfigure(3, weight=1)

        ttk.Label(log_card, text="Activity Log", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        self.log_text: scrolledtext.ScrolledText = scrolledtext.ScrolledText(log_card, wrap="word", height=10, bg="#f6f7fb", fg="#2f3b51", relief="flat", bd=0, highlightthickness=1, highlightbackground="#d9dee9")
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

    def save_history(self) -> None:
        history: dict[str, list[str]] = {
            "elf_files": [str(item) for item in self.elf_listbox.get(0, tk.END)],
            "map_files": [str(item) for item in self.map_listbox.get(0, tk.END)],
            "template_files": [str(item) for item in self.template_listbox.get(0, tk.END)]
        }
        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    def generate_a2l(self) -> None:
        try:
            elf_sel = str(self.elf_listbox.get(tk.ACTIVE))
            map_sel = str(self.map_listbox.get(tk.ACTIVE))
            if not elf_sel or not map_sel:
                messagebox.showerror("Error", "Please select both ELF and MAP files.")
                return

            template_sel = self._get_selected_template()
            advanced_mode = bool(self.advanced_var.get())
            output_name = self.output_var.get() or os.path.splitext(os.path.basename(elf_sel))[0] + ".a2l"
            output_path = os.path.join(os.path.dirname(elf_sel), output_name)

            self.logger.log(f"Compiler: {self.compiler_var.get()}")
            self.logger.log(f"Format: {self.format_var.get()}")
            self.logger.log(f"Parsing ELF: {elf_sel}")
            elf_symbols = parse_elf_fn(elf_sel)

            self.logger.log(f"Parsing MAP: {map_sel}")
            map_symbols = parse_map_fn(map_sel)

            selected_symbols = None
            if advanced_mode:
                selected_symbols = self._show_advanced_variable_selection(map_symbols)
                if selected_symbols is None:
                    self.logger.log("Generation cancelled by user.")
                    return
                self.logger.log(f"Advanced mode selected; generating {len(selected_symbols)} variables.")

            self.logger.log("Generating A2L...")
            generate_a2l_fn(elf_symbols, map_symbols, output_path, template_sel, selected_symbols, advanced_mode)

            self.logger.log("Generation successful.")
            self.open_button.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self.logger.log(f"Error: {exc}")

    def _get_selected_template(self) -> str | None:
        try:
            selected = str(self.template_listbox.get(tk.ACTIVE))
            return selected if selected else None
        except Exception:
            return None

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

    def _show_advanced_variable_selection(self, map_symbols: dict[str, Any]) -> list[str] | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Variable Selection")
        dialog.geometry("900x520")
        dialog.transient(self.root)
        dialog.grab_set()

        left_frame = ttk.Frame(dialog, padding=10)
        left_frame.pack(side="left", fill="both", expand=True)
        right_frame = ttk.Frame(dialog, padding=10)
        right_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(left_frame, text="Available MAP Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        left_listbox: Any = tk.Listbox(left_frame, selectmode=tk.EXTENDED, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        left_listbox.pack(fill="both", expand=True)

        ttk.Label(right_frame, text="Selected Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        right_listbox: Any = tk.Listbox(right_frame, selectmode=tk.EXTENDED, bd=0, highlightthickness=1, relief="solid", bg="#f6f7fb", activestyle="none")
        right_listbox.pack(fill="both", expand=True)

        control_frame = ttk.Frame(dialog, padding=10)
        control_frame.pack(fill="x")
        ttk.Button(control_frame, text=">> Add All", command=lambda: self._move_all(left_listbox, right_listbox)).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(control_frame, text="Add >", command=lambda: self._move_selected(left_listbox, right_listbox)).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(control_frame, text="< Remove", command=lambda: self._move_selected(right_listbox, left_listbox)).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(control_frame, text="<< Remove All", command=lambda: self._move_all(right_listbox, left_listbox)).pack(side="left", expand=True, fill="x", padx=4)

        button_frame = ttk.Frame(dialog, padding=10)
        button_frame.pack(fill="x")
        result: list[str] = []

        def on_ok() -> None:
            selected = [right_listbox.get(idx) for idx in range(right_listbox.size())]
            if not selected:
                messagebox.showwarning("Selection Required", "Please select at least one variable before generating A2L.")
                return
            nonlocal result
            result = selected
            dialog.destroy()

        def on_cancel() -> None:
            nonlocal result
            result = None
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok, style="Accent.TButton").pack(side="right", padx=8)
        ttk.Button(button_frame, text="Cancel", command=on_cancel, style="Secondary.TButton").pack(side="right")

        for symbol in sorted(map_symbols.keys()):
            left_listbox.insert(tk.END, symbol)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.root.wait_window(dialog)
        return result

    def _move_selected(self, source: tk.Listbox, destination: tk.Listbox) -> None:
        selections = list(source.curselection())
        for index in reversed(selections):
            value = source.get(index)
            destination.insert(tk.END, value)
            source.delete(index)

    def _move_all(self, source: tk.Listbox, destination: tk.Listbox) -> None:
        items = source.get(0, tk.END)
        for item in items:
            destination.insert(tk.END, item)
        source.delete(0, tk.END)

    def open_folder(self) -> None:
        import subprocess

        elf_sel = str(self.elf_listbox.get(tk.ACTIVE))
        if elf_sel:
            folder = os.path.dirname(elf_sel)
            subprocess.Popen(f'explorer "{folder}"')

