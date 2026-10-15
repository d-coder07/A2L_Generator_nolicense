from __future__ import annotations

import importlib.util
import argparse
import multiprocessing
import os
import subprocess
import sys
import tkinter as tk
from utils.resource_limits import DEFAULT_MEMORY_LIMIT_MB

REQUIRED_PACKAGES: list[str] = ["ttkbootstrap", "pyelftools"]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_package(package_name: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])


def ensure_dependencies(packages: list[str] | None = None) -> None:
    if is_frozen():
        return

    packages = packages or REQUIRED_PACKAGES
    missing: list[str] = []
    for package in packages:
        if importlib.util.find_spec(package) is None:
            missing.append(package)

    if not missing:
        return

    print(f"Installing missing dependencies: {', '.join(missing)}")
    for package in missing:
        install_package(package)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description="Generate an ASAP2 A2L file from an ELF and MAP file. "
                    "Run without arguments to open the GUI."
    )
    parser.add_argument("-elf", required=True, help="Input ELF file")
    parser.add_argument("-map", required=True, help="Input MAP file")
    parser.add_argument("-out", help="Output A2L file; defaults to the ELF name with .a2l")
    parser.add_argument("-jobs", type=int, choices=(1, 2), default=2,
                        help="Maximum ELF workers (large files use one); defaults to 2")
    parser.add_argument("-memory-limit", type=int, default=DEFAULT_MEMORY_LIMIT_MB,
                        help="Memory allowance in MiB; minimum 256, default 2048. System RAM reserve still applies")
    parser.add_argument(
        "-type",
        choices=("readonly", "readwrite", "read-only", "read-write"),
        default="readonly",
        help="Variable access mode; defaults to readonly"
    )
    parser.add_argument(
        "-expand",
        choices=("none", "arrays", "all"),
        default="none",
        help="Aggregate expansion: none, arrays, or all; defaults to none"
    )
    parser.add_argument(
        "-if-data",
        nargs="+",
        choices=("PROTOCOL_LAYER", "SEGMENT", "DAQ", "PAG", "PGM", "DAQ_EVENT",
                 "XCP_ON_CAN", "XCP_ON_SXL", "XCP_ON_TCP_IP", "XCP_ON_UDP_IP",
                 "XCP_ON_USB", "XCP_ON_FLX", "XCP_ON_ICP"),
        default=["PROTOCOL_LAYER", "DAQ", "DAQ_EVENT", "XCP_ON_CAN"],
        help="IF_DATA XCP tags; defaults to PROTOCOL_LAYER DAQ DAQ_EVENT XCP_ON_CAN"
    )
    return parser


def _run_headless(argv: list[str]) -> int:
    args = _build_argument_parser().parse_args(argv)
    elf_path = os.path.abspath(args.elf)
    map_path = os.path.abspath(args.map)

    missing = []
    if not os.path.isfile(elf_path):
        missing.append(f"ELF file not found: {elf_path}")
    if not os.path.isfile(map_path):
        missing.append(f"MAP file not found: {map_path}")
    if missing:
        for message in missing:
            print(f"Error: {message}", file=sys.stderr)
        return 2

    output_path = os.path.abspath(args.out) if args.out else os.path.splitext(elf_path)[0] + ".a2l"
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        print(f"Error: output directory not found: {output_dir}", file=sys.stderr)
        return 2

    access = "Read and Write (measurement + calibration)" if args.type in ("readwrite", "read-write") else "Read only (measurement)"

    try:
        from generator.a2l_generator import generate_a2l
        from parsers.elf_parser import parse_elf
        from parsers.map_parser import parse_map

        print(f"Parsing ELF: {elf_path}")
        print(f"Resource protection: up to {args.jobs} workers, {args.memory_limit} MiB memory allowance")
        elf_symbols = parse_elf(elf_path, expansion_mode=args.expand, jobs=args.jobs,
                    memory_limit_mb=args.memory_limit)
        print(f"Parsing MAP: {map_path}")
        map_symbols = parse_map(map_path)
        print(f"Generating A2L ({access}): {output_path}")
        generate_a2l(
            elf_symbols,
            map_symbols,
            output_path,
            selected_symbols=None,
            advanced_mode=False,
            if_data_tags=args.if_data,
            access=access,
            memory_limit_mb=args.memory_limit,
        )
    except Exception as exc:
        print(f"Error: A2L generation failed: {exc}", file=sys.stderr)
        return 1

    print(f"A2L generated successfully: {output_path}")
    return 0


def main() -> None:
    # Required so the ELF parser worker processes start correctly in the frozen build
    multiprocessing.freeze_support()

    # No arguments keeps the existing GUI workflow; any arguments select headless mode.
    if len(sys.argv) > 1:
        raise SystemExit(_run_headless(sys.argv[1:]))

    #if not is_frozen():
        #ensure_dependencies()

    from gui import A2LGeneratorGUI

    root = tk.Tk()
    A2LGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
