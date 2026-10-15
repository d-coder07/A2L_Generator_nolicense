from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from typing import Any, Callable, Dict, cast

try:
    import ttkbootstrap as ttk
    bootstrap_available = True
except Exception:
    from tkinter import ttk
    bootstrap_available = False

from app_info import APP_DEVELOPER, APP_VERSION
from generator.a2l_generator import generate_a2l
from parsers.elf_parser import parse_elf
from parsers.map_parser import parse_map
from utils.logger import Logger
from utils.resource_limits import DEFAULT_MEMORY_LIMIT_MB, ResourceGuard, ResourceLimitError

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
IF_DATA_OPTIONS = [
    "PROTOCOL_LAYER", "SEGMENT", "DAQ", "PAG", "PGM", "DAQ_EVENT",
    "XCP_ON_CAN", "XCP_ON_SXL", "XCP_ON_TCP_IP", "XCP_ON_UDP_IP",
    "XCP_ON_USB", "XCP_ON_FLX", "XCP_ON_ICP",
]
DEFAULT_IF_DATA_TAGS = ("PROTOCOL_LAYER", "DAQ", "DAQ_EVENT", "XCP_ON_CAN")


class A2LGeneratorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root: tk.Tk = root
        self._generating = False
        self.last_output_path: str | None = None
        self.root.title("A2L Generator")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 800)
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.style: Any = ttk.Style()
        self._apply_theme()

        main_frame = ttk.Frame(root, style="Panel.TFrame", padding=(24, 24, 24, 24))
        main_frame.pack(fill="both", expand=True)

        header_frame = ttk.Frame(main_frame, style="Panel.TFrame")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        header_frame.columnconfigure(0, weight=1)
        header = ttk.Label(header_frame, text="A2L Generation Dashboard", style="Header.TLabel")
        header.grid(row=0, column=0, sticky="w")
        self.about_button: Any = ttk.Button(
            header_frame, text="About", command=self.show_about, style="Secondary.TButton",
        )
        self.theme_switch: Any = ttk.Checkbutton(
            header_frame, text="Dark", variable=self.dark_mode_var,
            command=self.toggle_theme, style="Header.TCheckbutton",
        )
        self.theme_switch.grid(row=0, column=1, sticky="e", padx=(12, 8))
        self.about_button.grid(row=0, column=2, sticky="e")

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
        self._update_template_options()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def show_about(self) -> None:
        messagebox.showinfo(
            "About A2L Generator",
            f"A2L Generator\nVersion: {APP_VERSION}\nDeveloper: {APP_DEVELOPER}\n\n"
            "Generates ASAP2 A2L files from ELF/DWARF symbols and optional MAP files.\n\n"
            "Measurements and read/write calibration definitions\n"
            "Automatic or manual variable selection\n"
            "Array and structure expansion\n"
            "Configurable XCP IF_DATA tags\n"
            "Template cleaning or Only Update (No Cleaning)\n"
            "GUI and command-line generation\n\n"
            "Validate generated A2L files against your ECU configuration before use.",
            parent=self.root,
        )

    def _apply_theme(self) -> None:
        dark = self.dark_mode_var.get()
        self.colors = ({
            "panel": "#20262e", "card": "#2b333d", "text": "#e2e8f0",
            "heading": "#f5f7fa", "header": "#a8c9ff", "muted": "#b7c2cf",
            "list_bg": "#252d36", "list_fg": "#e2e8f0", "select_bg": "#365778",
            "select_fg": "#ffffff", "log_bg": "#252d36", "border": "#485461",
            "accent": "#397fce", "accent_fg": "#ffffff",
        } if dark else {
            "panel": "#f4f5f8", "card": "#ffffff", "text": "#2f3b51",
            "heading": "#1c2534", "header": "#1f3c88", "muted": "#5f6c7a",
            "list_bg": "#ffffff", "list_fg": "#253449", "select_bg": "#d8eaff",
            "select_fg": "#20364f", "log_bg": "#f6f7fb", "border": "#d9dee9",
            "accent": "#3984f4", "accent_fg": "#ffffff",
        })

        if bootstrap_available:
            preferred_theme = "darkly" if dark else "morph"
            available_themes = self.style.theme_names()
            self.style.theme_use(preferred_theme if preferred_theme in available_themes else "clam")
        else:
            self.style.theme_use("clam")

        self.root.configure(bg=self.colors["panel"])
        self.style.configure("TFrame", background=self.colors["panel"])
        self.style.configure("TLabel", font=("Segoe UI", 10), foreground=self.colors["text"], background=self.colors["panel"])
        self.style.configure("Header.TLabel", font=("Segoe UI Semibold", 16), foreground=self.colors["header"], background=self.colors["panel"])
        self.style.configure("CardHeader.TLabel", font=("Segoe UI Semibold", 12), foreground=self.colors["heading"], background=self.colors["card"])
        self.style.configure("Card.TLabel", foreground=self.colors["text"], background=self.colors["card"])
        self.style.configure("Tool.TLabel", font=("Segoe UI", 9), foreground=self.colors["muted"], background=self.colors["panel"])
        self.style.configure("Card.TCheckbutton", foreground=self.colors["text"], background=self.colors["card"])
        self.style.configure("Header.TCheckbutton", foreground=self.colors["text"], background=self.colors["panel"])
        self.style.configure("Card.TFrame", background=self.colors["card"], relief="flat")
        self.style.configure("Panel.TFrame", background=self.colors["panel"])
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=10,
                             background=self.colors["accent"], foreground=self.colors["accent_fg"])
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=10,
                             background=self.colors["card"], foreground=self.colors["text"])
        self.style.configure("TEntry", padding=8, fieldbackground=self.colors["list_bg"], foreground=self.colors["list_fg"])
        self.style.configure("TCombobox", padding=8, fieldbackground=self.colors["list_bg"],
                             foreground=self.colors["list_fg"], background=self.colors["card"])
        self.style.configure("TSpinbox", fieldbackground=self.colors["list_bg"], foreground=self.colors["list_fg"])
        self._apply_native_widget_colors(self.root)

    def _apply_native_widget_colors(self, parent: tk.Misc) -> None:
        for child in parent.winfo_children():
            if isinstance(child, tk.Listbox):
                child.configure(
                    bg=self.colors["list_bg"], fg=self.colors["list_fg"],
                    selectbackground=self.colors["select_bg"],
                    selectforeground=self.colors["select_fg"],
                )
            elif isinstance(child, tk.Text):
                child.configure(
                    bg=self.colors["log_bg"], fg=self.colors["text"],
                    insertbackground=self.colors["text"],
                    highlightbackground=self.colors["border"],
                )
            elif isinstance(child, tk.Frame):
                child.configure(bg=self.colors["panel"])
            self._apply_native_widget_colors(child)

    def toggle_theme(self) -> None:
        self._apply_theme()
        self.save_history()

    def _on_close(self) -> None:
        """Persist selected files and output name before closing the GUI."""
        if self._generating:
            messagebox.showwarning("Generation in Progress", "Generation is still running.", parent=self.root)
            return
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
        self.elf_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, exportselection=False,
                           bd=0, highlightthickness=1, relief="solid", bg="#ffffff",
                           fg="#253449", selectbackground="#d8eaff",
                           selectforeground="#20364f", activestyle="none")
        self.elf_listbox.grid(row=0, column=0, sticky="nsew", pady=(22, 4))
        self.elf_listbox.bind("<<ListboxSelect>>", self._on_elf_selection_changed)

        elf_btn = ttk.Frame(card, style="Card.TFrame")
        elf_btn.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        elf_btn.columnconfigure(0, weight=1)
        elf_btn.columnconfigure(1, weight=1)
        ttk.Button(elf_btn, text="Add ELF", command=self.add_elf, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(elf_btn, text="Remove ELF", command=self.remove_elf, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # --- MAP ---
        ttk.Label(card, text="MAP Files", style="CardHeader.TLabel").grid(row=2, column=0, sticky="nw", pady=(0, 4))
        self.map_listbox: Any = tk.Listbox(card, height=4, selectmode=tk.SINGLE, exportselection=False,
                           bd=0, highlightthickness=1, relief="solid", bg="#ffffff",
                           fg="#253449", selectbackground="#d8eaff",
                           selectforeground="#20364f", activestyle="none")
        self.map_listbox.grid(row=2, column=0, sticky="nsew", pady=(22, 4))

        map_btn = ttk.Frame(card, style="Card.TFrame")
        map_btn.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        map_btn.columnconfigure(0, weight=1)
        map_btn.columnconfigure(1, weight=1)
        ttk.Button(map_btn, text="Add MAP", command=self.add_map, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(map_btn, text="Remove MAP", command=self.remove_map, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # --- Optional Template ---
        ttk.Label(card, text="Optional A2L Template", style="CardHeader.TLabel").grid(row=4, column=0, sticky="nw", pady=(0, 4))
        self.template_listbox: Any = tk.Listbox(card, height=3, selectmode=tk.SINGLE, exportselection=False,
                            bd=0, highlightthickness=1, relief="solid", bg="#ffffff",
                            fg="#253449", selectbackground="#d8eaff",
                            selectforeground="#20364f", activestyle="none")
        self.template_listbox.grid(row=4, column=0, sticky="nsew", pady=(22, 4))

        tmpl_btn = ttk.Frame(card, style="Card.TFrame")
        tmpl_btn.grid(row=5, column=0, sticky="ew")
        tmpl_btn.columnconfigure(0, weight=1)
        tmpl_btn.columnconfigure(1, weight=1)
        ttk.Button(tmpl_btn, text="Add Template", command=self.add_template, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(tmpl_btn, text="Remove Template", command=self.remove_template, style="Secondary.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.only_update_var = tk.BooleanVar(value=False)
        self.only_update_checkbox: Any = ttk.Checkbutton(
            card, text="Only Update (No Cleaning)", variable=self.only_update_var,
            state="disabled", style="Card.TCheckbutton",
        )
        self.only_update_checkbox.grid(row=6, column=0, sticky="w", pady=(10, 0))

    def _build_options_section(self, parent: tk.Misc) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(18, 18, 18, 12))
        card.pack(fill="both", expand=True)

        # Action bar is packed first so it keeps its space when the window shrinks
        button_frame = ttk.Frame(card, style="Card.TFrame")
        button_frame.pack(side="bottom", fill="x", pady=(10, 0))
        self.generate_button: Any = ttk.Button(button_frame, text="Generate A2L", command=self.generate_a2l, style="Accent.TButton")
        self.generate_button.pack(fill="x")
        self.open_button: Any = ttk.Button(button_frame, text="Open A2L Folder", command=self.open_a2l_folder, state="disabled", style="Secondary.TButton")
        self.open_button.pack(fill="x", pady=(6, 0))

        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Generation Settings", style="CardHeader.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8),
        )
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Variable Access", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 3))
        ttk.Label(body, text="Output A2L File", style="Card.TLabel").grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(0, 3))
        self.access_var: Any = tk.StringVar(value=ACCESS_OPTIONS[0])
        self.access_dropdown: Any = ttk.Combobox(body, textvariable=self.access_var, values=ACCESS_OPTIONS, state="readonly")
        self.access_dropdown.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.output_var: Any = tk.StringVar()
        self.output_entry: Any = ttk.Entry(body, textvariable=self.output_var)
        self.output_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(0, 8))

        ttk.Label(body, text="IF_DATA XCP tags", style="Card.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 2))
        self.if_data_vars: dict[str, tk.BooleanVar] = {}
        tag_frame = ttk.Frame(body, style="Card.TFrame")
        tag_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        for column in range(2):
            tag_frame.columnconfigure(column, weight=1)
        for index, tag in enumerate(IF_DATA_OPTIONS):
            selected = tk.BooleanVar(value=tag in DEFAULT_IF_DATA_TAGS)
            self.if_data_vars[tag] = selected
            ttk.Checkbutton(tag_frame, text=tag, variable=selected, style="Card.TCheckbutton").grid(
                row=index // 2, column=index % 2, sticky="w", padx=(0, 8), pady=0,
            )

        ttk.Label(body, text="Aggregate variables", style="Card.TLabel").grid(row=5, column=0, sticky="w", pady=(2, 2))
        ttk.Label(body, text="Resource limits", style="Card.TLabel").grid(row=5, column=1, sticky="w", padx=(10, 0), pady=(2, 2))
        self.expand_all_var: Any = tk.BooleanVar(value=False)
        self.expand_arrays_var: Any = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Extended A2L (expand all structures, unions and arrays)", style="Card.TCheckbutton",
                variable=self.expand_all_var,
                command=self._on_expand_all_changed).grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(body, text="Expand arrays only", style="Card.TCheckbutton",
                variable=self.expand_arrays_var,
                command=self._on_expand_arrays_changed).grid(row=7, column=0, sticky="w")

        self.advanced_var: Any = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="Advanced mode (pick variables and access individually)", style="Card.TCheckbutton",
                        variable=self.advanced_var).grid(row=8, column=0, sticky="w", pady=(0, 2))

        resource_frame = ttk.Frame(body, style="Card.TFrame")
        resource_frame.grid(row=6, column=1, rowspan=3, sticky="nsew", padx=(10, 0))
        resource_frame.columnconfigure(0, weight=1)
        resource_frame.columnconfigure(1, weight=1)
        ttk.Label(resource_frame, text="ELF workers", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(resource_frame, text="Memory budget (MiB)", style="Card.TLabel").grid(row=0, column=1, sticky="w")
        self.jobs_var = tk.IntVar(value=2)
        self.memory_limit_var = tk.IntVar(value=DEFAULT_MEMORY_LIMIT_MB)
        ttk.Spinbox(resource_frame, from_=1, to=2, textvariable=self.jobs_var, width=6).grid(
            row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 0),
        )
        ttk.Spinbox(resource_frame, from_=256, to=8192, increment=256,
                    textvariable=self.memory_limit_var, width=8).grid(
            row=1, column=1, sticky="ew", pady=(2, 0),
        )

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
            self.elf_listbox.selection_clear(0, tk.END)
            self.elf_listbox.selection_set(tk.END)
            self.elf_listbox.activate(tk.END)
            self._set_default_output_name(file_path)
            self.save_history()

    def remove_elf(self) -> None:
        selection = self.elf_listbox.curselection()
        if selection:
            self.elf_listbox.delete(selection[0])
            self.save_history()

    def _set_default_output_name(self, elf_path: str) -> None:
        default_name = os.path.splitext(os.path.basename(elf_path))[0] + ".a2l"
        self.output_var.set(default_name)

    def _on_elf_selection_changed(self, _event: tk.Event | None = None) -> None:
        elf_path = self._get_single_selection(self.elf_listbox)
        if elf_path:
            self._set_default_output_name(elf_path)

    def add_map(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Map files", "*.map")])
        if file_path:
            self.map_listbox.insert(tk.END, file_path)
            self.map_listbox.selection_clear(0, tk.END)
            self.map_listbox.selection_set(tk.END)
            self.map_listbox.activate(tk.END)
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
                history: dict[str, Any] = json.load(f)
            for path in history.get("elf_files", []):
                self.elf_listbox.insert(tk.END, path)
            for path in history.get("map_files", []):
                self.map_listbox.insert(tk.END, path)
            for path in history.get("template_files", []):
                self.template_listbox.insert(tk.END, path)
            self.only_update_var.set(bool(history.get("only_update", False)))
            self.jobs_var.set(max(1, min(2, int(history.get("parser_jobs", 2)))))
            self.memory_limit_var.set(max(256, min(8192, int(history.get("memory_limit_mb", DEFAULT_MEMORY_LIMIT_MB)))))
            self.output_var.set(history.get("output_name", ""))
            self.dark_mode_var.set(bool(history.get("dark_mode", False)))
            self._apply_theme()
        except Exception:
            pass

    def save_history(self) -> None:
        history: dict[str, Any] = {
            "elf_files": [str(item) for item in self.elf_listbox.get(0, tk.END)],
            "map_files": [str(item) for item in self.map_listbox.get(0, tk.END)],
            "template_files": [str(item) for item in self.template_listbox.get(0, tk.END)],
            "only_update": self.only_update_var.get(),
            "parser_jobs": self.jobs_var.get(),
            "memory_limit_mb": self.memory_limit_var.get(),
            "dark_mode": self.dark_mode_var.get(),
            "output_name": self.output_var.get(),
        }
        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    def _run_background(self, operation: Callable[[], Any]) -> Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(operation)
            finished = tk.BooleanVar(master=self.root, value=False)

            def poll() -> None:
                if future.done():
                    finished.set(True)
                else:
                    self.root.after(50, poll)

            if not future.done():
                self.root.after(0, poll)
                self.root.wait_variable(finished)
            return future.result()

    def generate_a2l(self) -> None:
        if self._generating:
            return
        self._generating = True
        self.generate_button.config(state="disabled")
        self.open_button.config(state="disabled")
        self.last_output_path = None
        generation_started: float | None = None
        try:
            jobs = self.jobs_var.get()
            memory_limit_mb = self.memory_limit_var.get()
            if jobs not in (1, 2) or not 256 <= memory_limit_mb <= 8192:
                raise ValueError("Choose 1 or 2 ELF workers and a memory budget from 256 to 8192 MiB.")
            guard = ResourceGuard(memory_limit_mb)
            guard.check(force=True)
            elf_sel = self._get_single_selection(self.elf_listbox)
            map_sel = self._get_single_selection(self.map_listbox)
            if not elf_sel:
                messagebox.showerror("Error", "Please select an ELF file.")
                return

            template_sel = self._get_selected_template()
            advanced_mode = bool(self.advanced_var.get())
            output_name = self.output_var.get() or os.path.splitext(os.path.basename(elf_sel))[0] + ".a2l"
            output_name = os.path.basename(output_name)
            elf_directory = os.path.dirname(os.path.abspath(elf_sel))
            output_path = os.path.join(elf_directory, output_name)
            self.output_var.set(output_name)
            self.save_history()

            generation_started = time.perf_counter()
            self.logger.log(f"Access: {self.access_var.get()}")
            self.logger.log(f"Parsing ELF: {elf_sel}")
            started = time.perf_counter()
            expansion_mode = self._expansion_mode()
            self.logger.log(f"Aggregate expansion: {expansion_mode}")
            self.logger.log(f"Resource protection: maximum {jobs} workers, {memory_limit_mb} MiB; large ELFs use one worker.")
            elf_symbols = self._run_background(lambda: parse_elf_fn(
                elf_sel, expansion_mode=expansion_mode, jobs=jobs, memory_limit_mb=memory_limit_mb,
            ))
            self.logger.log(f"Found {len(elf_symbols) - 1} data symbols in {time.perf_counter() - started:.1f} s.")

            map_symbols = {}
            if map_sel:
                self.logger.log(f"Parsing MAP: {map_sel}")
                guard.check(additional_bytes=os.path.getsize(map_sel) * 8, force=True)
                map_symbols = self._run_background(lambda: parse_map_fn(map_sel))
                guard.check(force=True)

            selected_symbols = None
            if advanced_mode:
                selected_symbols = self._show_advanced_variable_selection(elf_symbols)
                if selected_symbols is None:
                    self.logger.log("Generation cancelled by user.")
                    return
                self.logger.log(f"Advanced mode selected; generating {len(selected_symbols)} variables.")

            self.logger.log("Generating A2L...")
            only_update = bool(template_sel and self.only_update_var.get())
            if only_update:
                self.logger.log("Only Update: preserving template content and appending new definitions.")
            if_data_tags = self._get_selected_if_data_tags()
            access = self.access_var.get()
            self._run_background(lambda: generate_a2l_fn(
                elf_symbols, map_symbols, output_path, template_sel,
                selected_symbols, advanced_mode, if_data_tags, access,
                only_update=only_update, memory_limit_mb=memory_limit_mb,
            ))

            self.last_output_path = output_path
            self.logger.log("Generation successful.")
            self.open_button.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self.logger.log(f"Error: {exc}")
        finally:
            if generation_started is not None:
                elapsed = time.perf_counter() - generation_started
                self.logger.log(f"Total execution time: {elapsed:.2f} seconds.")
            self._generating = False
            self.generate_button.config(state="normal")

    def _get_selected_if_data_tags(self) -> list[str]:
        """Return the selected IF_DATA tags in the displayed order."""
        return [tag for tag in IF_DATA_OPTIONS if self.if_data_vars[tag].get()]

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

    def _update_template_options(self) -> None:
        has_template = self.template_listbox.size() > 0
        self.only_update_checkbox.config(state="normal" if has_template else "disabled")
        if not has_template:
            self.only_update_var.set(False)

    def add_template(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("A2L Template files", "*.a2l;*.txt"), ("All files", "*.*")])
        if file_path:
            self.template_listbox.insert(tk.END, file_path)
            self._update_template_options()
            self.save_history()

    def remove_template(self) -> None:
        selection = self.template_listbox.curselection()
        if selection:
            self.template_listbox.delete(selection[0])
            self._update_template_options()
            self.save_history()

    def _show_advanced_variable_selection(self, elf_symbols: dict[str, Any]) -> dict[str, str] | None:
        """Pick variables from the ELF data objects and assign read or read/write access."""
        guard = ResourceGuard(self.memory_limit_var.get())
        guard.check(additional_bytes=len(elf_symbols) * 512, force=True)
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Variable Selection")
        dialog.geometry("1000x600")
        dialog.minsize(760, 460)
        dialog.configure(bg=self.colors["panel"])
        dialog.transient(self.root)
        dialog.grab_set()

        available = elf_symbols
        available_names = sorted(
            name for name, info in elf_symbols.items()
            if name != "_enums" and info.get("size", 0) > 0
        )

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=0)
        dialog.columnconfigure(2, weight=1)
        dialog.rowconfigure(1, weight=1)

        filter_frame = ttk.Frame(dialog, style="Card.TFrame", padding=(10, 10, 10, 0))
        filter_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter").grid(row=0, column=0, padx=(0, 8))
        filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=filter_var).grid(row=0, column=1, sticky="ew")
        statics_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Statics only", variable=statics_var,
                style="Card.TCheckbutton").grid(row=0, column=2, padx=(10, 0))

        left_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        left_frame.grid(row=1, column=0, sticky="nsew")
        right_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        right_frame.grid(row=1, column=2, sticky="nsew")

        ttk.Label(left_frame, text="Available ELF Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        left_listbox: Any = tk.Listbox(
            left_frame, selectmode=tk.EXTENDED, exportselection=False, bd=0,
            highlightthickness=1, relief="solid", bg=self.colors["list_bg"],
            fg=self.colors["list_fg"], selectbackground=self.colors["select_bg"],
            selectforeground=self.colors["select_fg"], activestyle="none",
        )
        left_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=left_listbox.yview)
        left_listbox.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right", fill="y")
        left_listbox.pack(fill="both", expand=True)

        ttk.Label(right_frame, text="Selected Variables", style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        right_listbox: Any = tk.Listbox(
            right_frame, selectmode=tk.EXTENDED, exportselection=False, bd=0,
            highlightthickness=1, relief="solid", bg=self.colors["list_bg"],
            fg=self.colors["list_fg"], selectbackground=self.colors["select_bg"],
            selectforeground=self.colors["select_fg"], activestyle="none",
        )
        right_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=right_listbox.yview)
        right_listbox.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        right_listbox.pack(fill="both", expand=True)

        chosen: dict[str, str] = {}
        shown: list[str] = []

        def memory_ok() -> bool:
            if not dialog.winfo_exists():
                return False
            try:
                guard.check(force=True)
                return True
            except ResourceLimitError as exc:
                messagebox.showerror("Resource Protection", str(exc), parent=dialog)
                on_cancel()
                return False

        def label_for(name: str) -> str:
            info = available[name]
            tag = " [static]" if info.get("static") else ""
            return f'{name}  ({info.get("datatype", "?")} @ 0x{info.get("address", 0):08X}){tag}'

        def refresh_left() -> None:
            if not memory_ok():
                return
            needle = filter_var.get().strip().lower()
            statics_only = statics_var.get()
            shown.clear()
            left_listbox.delete(0, tk.END)
            for name in available_names:
                if name in chosen:
                    continue
                if statics_only and not available[name].get("static"):
                    continue
                if needle and needle not in name.lower():
                    continue
                shown.append(name)
            for start in range(0, len(shown), 1000):
                if not memory_ok():
                    return
                left_listbox.insert(tk.END, *(label_for(name) for name in shown[start:start + 1000]))

        def refresh_right() -> None:
            if not memory_ok():
                return
            right_listbox.delete(0, tk.END)
            ordered = sorted(chosen)
            for start in range(0, len(ordered), 1000):
                if not memory_ok():
                    return
                right_listbox.insert(tk.END, *(f'{name}  [{chosen[name].upper()}]' for name in ordered[start:start + 1000]))

        def add(access: str, everything: bool = False) -> None:
            if not memory_ok():
                return
            try:
                guard.check(additional_bytes=len(shown) * 128 if everything else 0, force=True)
            except ResourceLimitError as exc:
                messagebox.showerror("Resource Protection", str(exc), parent=dialog)
                on_cancel()
                return
            names = shown if everything else [shown[i] for i in left_listbox.curselection()]
            for name in names:
                chosen[name] = access
            refresh_left()
            refresh_right()

        def remove(everything: bool = False) -> None:
            ordered = sorted(chosen)
            names = ordered if everything else [ordered[index] for index in right_listbox.curselection()]
            for name in names:
                chosen.pop(name, None)
            refresh_left()
            refresh_right()

        control_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        control_frame.grid(row=1, column=1, sticky="ns")
        ttk.Button(control_frame, text="Add  >  Read", command=lambda: add("r")).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add  >  Read/Write", command=lambda: add("rw")).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add All  >  Read", command=lambda: add("r", True)).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="Add All  >  Read/Write", command=lambda: add("rw", True)).pack(fill="x", pady=3)
        ttk.Button(control_frame, text="<  Remove", command=lambda: remove()).pack(fill="x", pady=(16, 3))
        ttk.Button(control_frame, text="<<  Remove All", command=lambda: remove(True)).pack(fill="x", pady=3)

        button_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
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

        filter_trace = filter_var.trace_add("write", lambda *_a: refresh_left())
        statics_trace = statics_var.trace_add("write", lambda *_a: refresh_left())
        refresh_left()

        if not dialog.winfo_exists():
            return None
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.root.wait_window(dialog)
        filter_var.trace_remove("write", filter_trace)
        statics_var.trace_remove("write", statics_trace)
        return result

    def open_a2l_folder(self) -> None:
        output_path = self.last_output_path
        output_folder = os.path.dirname(output_path) if output_path else ""
        if not output_folder or not os.path.isdir(output_folder):
            messagebox.showerror("Error", "The generated A2L folder could not be found.", parent=self.root)
            return

        try:
            if sys.platform == "win32":
                os.startfile(output_folder)
            else:
                import subprocess

                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, output_folder])
        except OSError as exc:
            messagebox.showerror("Unable to Open A2L Folder", str(exc), parent=self.root)

