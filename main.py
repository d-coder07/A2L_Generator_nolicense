import importlib.util
import subprocess
import sys
import tkinter as tk

REQUIRED_PACKAGES = ["ttkbootstrap", "pyelftools"]


def is_frozen():
    return getattr(sys, "frozen", False)


def install_package(package_name):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])


def ensure_dependencies():
    if is_frozen():
        return

    missing = []
    for package in REQUIRED_PACKAGES:
        if importlib.util.find_spec(package) is None:
            missing.append(package)

    if not missing:
        return

    print(f"Installing missing dependencies: {', '.join(missing)}")
    for package in missing:
        install_package(package)


def main():
    if not is_frozen():
        ensure_dependencies()

    from gui import A2LGeneratorGUI

    root = tk.Tk()
    app = A2LGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
