#!/usr/bin/env python3
"""
Build script for creating A2L Generator executable and release artifacts.
Supports Windows .exe, tar.gz, and zip distributions.
"""

import os
import sys
import subprocess
import shutil
import zipfile
import tarfile
from pathlib import Path
from datetime import datetime

from app_info import APP_DEVELOPER, APP_VERSION


def get_version():
    """Use shared application version unless the build environment overrides it."""
    env_version = os.getenv("VERSION") or os.getenv("BUILD_VERSION")
    if env_version:
        return env_version.lstrip("v")

    return APP_VERSION


def install_pyinstaller():
    """Install PyInstaller if not already installed."""
    try:
        import PyInstaller
        print("PyInstaller already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("PyInstaller installed")


def build_executable():
    """Build Windows executable with PyInstaller."""
    version = get_version()
    dist_dir = Path("dist")
    build_dir = Path("build")
    
    # Clean previous builds
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    print(f"\nBuilding A2L Generator v{version}...")
    
    add_data_sep = ";" if os.name == "nt" else ":"
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name", "A2LGenerator",
        "--onefile",
        # Keep a console so headless invocations can report progress and errors.
        "--console",
        "--icon=icon.ico" if Path("icon.ico").exists() else "",
        "--add-data", f"config{add_data_sep}config",
        "--add-data", f"parsers{add_data_sep}parsers",
        "--add-data", f"generator{add_data_sep}generator",
        "--add-data", f"utils{add_data_sep}utils",
        "--collect-all", "tkinter",
        "--collect-all", "ttkbootstrap",
        "--collect-all", "elftools",
        "--hidden-import=tkinter",
        "--hidden-import=ttkbootstrap",
        "--hidden-import=elftools",
        "main.py",
    ]
    
    # Remove empty strings from command
    cmd = [c for c in cmd if c]
    
    result = subprocess.run(cmd)
    if result.returncode == 0:
        exe_path = dist_dir / "A2LGenerator.exe"
        print(f"Executable built: {exe_path}")
        return exe_path, version
    else:
        print("Build failed")
        sys.exit(1)


def create_release_artifacts(exe_path, version):
    """Create release artifacts (.zip, .tar.gz, etc)."""
    dist_dir = Path("dist")
    releases_dir = Path("releases")
    releases_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    base_name = f"A2LGenerator-v{version}-{timestamp}"
    
    print(f"\nCreating release artifacts...")
    
    # Create zip file
    zip_name = releases_dir / f"{base_name}-windows.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname="A2LGenerator.exe")
        zf.write("README.md", arcname="README.md")
        zf.write("LICENSE", arcname="LICENSE")
        if Path("config").exists():
            for config_file in Path("config").glob("*"):
                zf.write(config_file, arcname=f"config/{config_file.name}")
    print(f"ZIP created: {zip_name} ({zip_name.stat().st_size / (1024*1024):.2f} MB)")
    
    # Create tar.gz file
    tar_name = releases_dir / f"{base_name}-windows.tar.gz"
    with tarfile.open(tar_name, 'w:gz') as tf:
        tf.add(exe_path, arcname="A2LGenerator.exe")
        tf.add("README.md", arcname="README.md")
        tf.add("LICENSE", arcname="LICENSE")
        if Path("config").exists():
            for config_file in Path("config").glob("*"):
                tf.add(config_file, arcname=f"config/{config_file.name}")
    print(f"TAR.GZ created: {tar_name} ({tar_name.stat().st_size / (1024*1024):.2f} MB)")
    
    return str(zip_name), str(tar_name)


def create_release_notes(version):
    """Create release notes template."""
    releases_dir = Path("releases")
    releases_dir.mkdir(exist_ok=True)
    readme_path = Path(__file__).resolve().parent / "README.md"
    change_history = ""
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        if "## Change History\n" in readme:
            change_history = "\n## Change History\n" + readme.split("## Change History\n", 1)[1].split("\n## ", 1)[0].strip() + "\n"
    
    release_notes = f"""# A2L Generator v{version}

**Developer**: {APP_DEVELOPER}

## Release Notes

### Features
- Modern Windows 11 UI with ttkbootstrap
- Advanced ELF parser with DWARF debug symbol support
- Automatic enum type detection and extraction
- Floating-point scaling factor extraction
- Multi-format A2L output (Classic, Extended, AUTOSAR)
- Automatic ELF/DWARF parsing for GCC, IAR, ARMCC, TASKING, and HighTec outputs
- Session history persistence
- Real-time activity logging
- About dialog with version, developer, capability summary, and validation reminder
- Only Update (No Cleaning) template preservation with duplicate prevention
- Automatic or manual variable selection with read/write calibration access
- Aggregate expansion and configurable XCP IF_DATA tags
- GUI and headless command-line generation

{change_history}

### Technical Details
- **Python Runtime**: Bundled (no Python installation required)
- **Dependencies**: Bundled in executable; manually installed for source runs. No startup package installation.
- **License**: Apache License 2.0 (Enterprise-friendly)
- **Size**: Standalone executable ~50-80 MB

### Installation
1. Download the .zip or .tar.gz file
2. Extract to your desired location
3. Run `A2LGenerator.exe`
4. Select ELF/MAP files and generate A2L output

### Known Limitations
- MAP file parser is basic and works with simple symbol/address/size lines
- Currently supports Windows platform

### License
Apache License 2.0 - Suitable for enterprise and commercial use.

---
**Release Date**: {datetime.now().strftime("%Y-%m-%d")}
**Platform**: Windows 10/11
"""
    
    notes_file = releases_dir / f"RELEASE_NOTES_v{version}.md"
    notes_file.write_text(release_notes, encoding="utf-8")
    print(f"Release notes: {notes_file}")
    return notes_file


def main():
    """Main build process."""
    print("=" * 60)
    print("A2L Generator - Build & Release System")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Run this script from project root.")
        sys.exit(1)
    
    # Step 1: Install PyInstaller
    install_pyinstaller()
    
    # Step 2: Build executable
    exe_path, version = build_executable()
    
    # Step 3: Create release artifacts
    zip_path, tar_path = create_release_artifacts(exe_path, version)
    
    # Step 4: Create release notes
    notes_path = create_release_notes(version)
    
    print("\n" + "=" * 60)
    print("Build Complete!")
    print("=" * 60)
    print(f"\n📌 Release v{version} Artifacts:")
    print(f"   • Executable: {exe_path}")
    print(f"   • ZIP: {zip_path}")
    print(f"   • TAR.GZ: {tar_path}")
    print(f"   • Notes: {notes_path}")
    print(f"\n📤 Next Steps:")
    print(f"   1. Test the executable: {exe_path}")
    print(f"   2. Upload to GitHub Releases")
    print(f"   3. Create tag: git tag -a v{version}")
    print(f"   4. Push: git push origin --tags")


if __name__ == "__main__":
    main()
