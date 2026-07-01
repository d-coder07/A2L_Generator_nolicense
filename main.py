from __future__ import annotations

import importlib.util
import subprocess
import sys
import tkinter as tk

REQUIRED_PACKAGES: list[str] = ["ttkbootstrap", "pyelftools"]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_package(package_name: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])


def ensure_dependencies() -> None:
    if is_frozen():
        return

    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        if importlib.util.find_spec(package) is None:
            missing.append(package)

    if not missing:
        return

    print(f"Installing missing dependencies: {', '.join(missing)}")
    for package in missing:
        install_package(package)


def main() -> None:
    if not is_frozen():
        ensure_dependencies()

    from gui import A2LGeneratorGUI

    root = tk.Tk()
    A2LGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
