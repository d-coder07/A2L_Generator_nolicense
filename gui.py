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
except ModuleNotFoundError:
    from tkinter import ttk
    bootstrap_available = False

from generator.a2l_generator import generate_a2l
from parsers.elf_parser import parse_elf
from parsers.map_parser import parse_map
from parsers.metadata_parser import parse_metadata
from utils.logger import Logger

parse_elf_fn = cast(Callable[[str], dict[str, Any]], parse_elf)
parse_map_fn = cast(Callable[[str], Any], parse_map)
parse_metadata_fn = cast(Callable[[str], dict[str, Any]], parse_metadata)
generate_a2l_fn = cast(Callable[[dict[str, Any], Any, dict[str, Any], str], None], generate_a2l)


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
            self.save_history()

    def remove_elf(self) -> None:
        selection = self.elf_listbox.curselection()
        if selection:
            self.elf_listbox.delete(selection[0])
            self.save_history()

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
            "map_files": [str(item) for item in self.map_listbox.get(0, tk.END)]
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

            output_name = self.output_var.get() or os.path.splitext(os.path.basename(elf_sel))[0] + ".a2l"
            output_path = os.path.join(os.path.dirname(elf_sel), output_name)

            self.logger.log(f"Compiler: {self.compiler_var.get()}")
            self.logger.log(f"Format: {self.format_var.get()}")
            self.logger.log(f"Parsing ELF: {elf_sel}")
            elf_symbols = parse_elf_fn(elf_sel)

            self.logger.log(f"Parsing MAP: {map_sel}")
            map_symbols = parse_map_fn(map_sel)

            metadata: dict[str, Any] = {}
            meta_file = "config/metadata.csv"
            if os.path.exists(meta_file):
                self.logger.log(f"Parsing Metadata: {meta_file}")
                metadata = parse_metadata_fn(meta_file)

            self.logger.log("Generating A2L...")
            generate_a2l_fn(elf_symbols, map_symbols, metadata, output_path)

            self.logger.log("Generation successful.")
            self.open_button.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self.logger.log(f"Error: {exc}")

    def open_folder(self) -> None:
        import subprocess

        elf_sel = str(self.elf_listbox.get(tk.ACTIVE))
        if elf_sel:
            folder = os.path.dirname(elf_sel)
            subprocess.Popen(f'explorer "{folder}"')

