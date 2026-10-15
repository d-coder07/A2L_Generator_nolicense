# A2L Generator

**Version: 2.1.0** | **Developer: DevD**

A modern, feature-rich GUI-based A2L (ASAP2) file generator for embedded automotive development. This tool extracts symbol information from ELF binaries and MAP files, automatically detects enums and floating-point scaling factors, and generates compliant A2L files for GCC, IAR, ARMCC, TASKING, and HighTec ELF/DWARF toolchains without requiring a compiler selection.

## 📥 Downloads & Releases

The current source version is **2.1.0**. Previously published standalone downloads are listed below; a 2.1.0 executable must be built and published separately.

| Release | Format | Size | Download |
|---------|--------|------|----------|
| **v2.1.0 ** | Windows .exe ZIP Archive | 22.8 MB | [Release](https://github.com/d-coder07/A2L_Generator_nolicense/releases/tag/v2.1.0) |
|| TAR.GZ Archive | 22.8 MB | [Release](https://github.com/d-coder07/A2L_Generator_nolicense/releases/tag/v2.1.0) |

👉 **[View All Releases →](https://github.com/d-coder07/A2L_Generator_nolicense/releases)**

### ✨ Beta & Development Releases

Pre-release versions available for early access:
- **v1.1.0-beta** - MAP file parser improvements, enhanced DWARF support
- **v1.0.0-alpha** - Community preview, all core features

### 🚀 Quick Start with Executable

1. Download the `.zip` or `.tar.gz` file from Releases
2. Extract to a folder
3. Double-click `A2LGenerator.exe`
4. No Python installation required!

## Features

- **Modern Windows 11-Inspired UI**: Professional, responsive interface with card-based layout
- **Tool Information**: Header About button displays version 2.1.0, developer DevD, capabilities, and a validation reminder
- **Light and Dark Themes**: Header switch changes the complete GUI palette and remembers the choice between sessions
- **Explicit Dependency Installation**: Application startup does not install packages; install source dependencies manually
- **Template Preservation**: Only Update (No Cleaning) appends new definitions without removing or overwriting existing template content
- **Resource Protection**: Conservative worker counts, RAM/commit checks, lower-priority Windows parsing, and background GUI generation
- **Advanced ELF Parsing**:
  - DWARF debug symbol extraction
  - Automatic enum type detection
  - Floating-point scaling factor detection
  - Comprehensive type mapping (signed/unsigned integers, IEEE floats)
- **Multi-Format Support**: Classic A2L, Extended A2L, AUTOSAR A2L
- **File Management**: Add/remove ELF and MAP files with session history
- **Real-Time Logging**: Activity log shows generation progress and results
- **Compiler Support**: Automatic ELF/DWARF parsing for GCC, IAR, ARMCC, TASKING, and HighTec outputs
- **Cross-Platform**: Works on Windows with Python 3.7+

## Requirements

- Python 3.7 or higher
- Required packages (install manually when running from source):
  - `pyelftools` - ELF binary parsing with DWARF support
  - `ttkbootstrap` - Modern themed Tkinter widgets

## Installation

1. Clone the repository:
```bash
git clone https://github.com/d-coder07/A2L_Generator_nolicense.git
cd A2L_Generator
```

2. Install dependencies and run the application:
```bash
python -m pip install -r requirements.txt
python main.py
```

Automatic package installation at application startup is disabled. Packaged executables include their runtime dependencies.

## Usage

1. **Launch the App**: `python main.py`
2. **Add Source Files**:
   - Click "Add ELF" to select an ELF binary
   - Click "Add MAP" to select a MAP file
3. **Configure Generation**:
  - Choose read-only or read/write variable access
  - Specify output file path when needed
  - Optionally add an A2L template and select **Only Update (No Cleaning)** to preserve all existing content and append new variable definitions at the end of the module. This works with automatic generation and manual variable selection. Existing definitions with matching names are retained, not overwritten or duplicated. Leave the checkbox unchecked to use the existing template-cleaning behavior.
4. **Generate A2L**: Click "Generate A2L"
5. **View Results**: Check the Activity Log for progress and status
6. **Open Output**: Click "Open Folder" to view generated A2L file
7. **Tool Information**: Click "About" in the header to view the version, developer, and capability summary

### Large ELF Files and Resource Protection

- **Maximum ELF workers** defaults to 2, capped at half the detected logical cores. Files of 64 MiB or larger, low-RAM situations, and small memory budgets use one worker automatically.
- **Memory budget (MiB)** defaults to 2048. The GUI accepts 256 to 8192 MiB. Parallel workers and the merging process share this allowance; serial parsing and output generation check their own process memory against it.
- The tool reserves at least **1 GiB**, scaling to 10% of physical RAM up to a 4 GiB cap, and on Windows checks remaining system commit capacity as well. Raising the memory budget does not disable the system reserve.
- Resource protection checks before large allocations and during DWARF processing, symbol/aggregate expansion, advanced selection, and A2L definition generation. When protection trips, generation stops with an error rather than silently omitting variables or retrying another expensive parse. Output is not opened until generation and the final memory check succeed.
- Windows parsing runs at below-normal process priority, restored afterward. Background parsing/generation keeps Tk's event loop active, and the Generate button prevents concurrent runs. Closing the main window is blocked while generation is active.
- Completed compilation-unit DIE caches are released using the pinned pyelftools 0.33 cache layout. Scalar-array metadata is resolved once per array; compact mode skips aggregate expansion. Cached results remain available on repeat runs, and advanced-selection lists use batched insertion.

These are **cooperative safeguards**, not an OS-enforced memory or CPU-percentage limit. A single library allocation can occur between checks, and other applications can change available memory abruptly. Compact aggregate mode (`-expand none`) is recommended when individual array elements or structure members are not needed; full expansion can produce many more variables than the ELF contains at the root level.

### Headless Command Line Usage

Run `main.py` with arguments to generate an A2L without opening the GUI. The ELF and MAP files are required. The output defaults to the ELF filename with an `.a2l` extension, and access defaults to read-only.

```bash
python main.py -elf "C:\\Data\\Project.elf" -map "C:\\Data\\Project.map"
python main.py -elf "C:\\Data\\Project.elf" -map "C:\\Data\\Project.map" -out "C:\\Data\\Project.a2l" -type readwrite -expand all
python main.py -elf "C:\\Data\\Project.elf" -map "C:\\Data\\Project.map" -if-data PROTOCOL_LAYER DAQ DAQ_EVENT XCP_ON_CAN
python main.py -elf "C:\\Data\\Project.elf" -map "C:\\Data\\Project.map" -expand all -jobs 1 -memory-limit 2048
```

Supported access values are `readonly`, `readwrite`, `read-only`, and `read-write`. Use `-expand none` for compact root variables, `-expand arrays` for array expansion, or `-expand all` for structures, unions, and arrays. Select one or more `-if-data` tags from `PROTOCOL_LAYER`, `SEGMENT`, `DAQ`, `PAG`, `PGM`, `DAQ_EVENT`, `XCP_ON_CAN`, `XCP_ON_SXL`, `XCP_ON_TCP_IP`, `XCP_ON_UDP_IP`, `XCP_ON_USB`, `XCP_ON_FLX`, and `XCP_ON_ICP`. The default is `PROTOCOL_LAYER DAQ DAQ_EVENT XCP_ON_CAN`; default values, including CAN IDs `0x400007A0` and `0x400007A1`, are used until ECU-specific configuration is added. Missing input files or output directories are reported on the console and return a nonzero exit code. Advanced variable selection is GUI-only; headless mode processes all eligible ELF data objects.

Use `-jobs 1` or `-jobs 2` to set the maximum worker count and `-memory-limit <MiB>` to set the memory allowance (minimum 256, default 2048). Large files and low memory headroom still force a single worker. No new packages or automatic installation are required for resource protection on Windows.

The packaged executable uses the same interface:

```bash
A2LGenerator.exe -elf "C:\\Data\\Project.elf" -map "C:\\Data\\Project.map" -out "C:\\Data\\Project.a2l" -type readonly -if-data PROTOCOL_LAYER DAQ DAQ_EVENT XCP_ON_CAN
```

## Change History

### 2.1.0 - 2026-10-15

- Added a compact About button and dialog with tool version, developer **DevD**, capability summary, and ECU validation reminder.
- Added a persistent header switch for light/dark appearance, including native file lists, logs, and advanced selection dialog.
- Centralized version **2.1.0** and developer metadata in `app_info.py`; GUI and release tooling use the same version by default. Build environment version overrides remain supported.
- Added **Only Update (No Cleaning)** for A2L templates: preserve existing content and append new generated definitions before the module ends.
- Enabled template updates for both automatic generation and manual variable selection, including read/write calibration definitions and their supporting layouts and conversions.
- Retained existing matching definitions instead of overwriting or duplicating them; preserved template line endings and unchanged content.
- Saved the template-update option in session history and disabled it when no template is present. Unchecked mode retains the original cleaning behavior.
- Disabled automatic package installation at application startup; source dependencies must be installed manually.
- Added focused template-update regression tests and checked GUI information-button layout at default and minimum window sizes.
- Updated installation instructions, tool information, and generated release notes.
- Added configurable worker/memory budgets, Windows RAM and commit safeguards, and lower-priority ELF parsing. Large ELFs use one worker; memory failures and terminated workers are not retried.
- Reduced retained DWARF data by releasing completed CU DIE caches, skipping unused expansion, resolving scalar-array metadata once, and merging worker results incrementally.
- Moved heavy GUI work off the Tk thread, blocked overlapping runs, and optimized advanced selection with one sorted name index and batched list updates.
- Added regression coverage for worker caps, memory reserves, allocation preflights, expansion modes, cache release, and protected output.

### 2.0.0 - Previously Documented Stable Release

- Previously published Windows executable ZIP and TAR.GZ downloads, listed at 22.8 MB each.
- The existing tool capabilities carried into 2.1.0 include GUI and headless generation, automatic ELF/DWARF compiler handling, measurement and calibration access modes, aggregate expansion, configurable XCP IF_DATA, manual variable selection, and session history.

### 1.2.0 - Earlier Documented Stable Release

- Standalone Windows executable and ZIP/TAR.GZ distribution packages.

### 1.1.0-beta

- MAP parser improvements and enhanced DWARF support, as documented in the pre-release summary.

### 1.0.0-alpha

- Community preview of the core generation features.

Historical entries summarize available release documentation; no unavailable commit history or release dates are inferred.

## Project Structure

```
A2L_Generator/
├── main.py              # GUI and headless entry point
├── app_info.py          # Shared tool version and developer metadata
├── gui.py               # Modern Windows 11 UI implementation
├── config/
│   └── history.json     # Session history
├── parsers/
│   ├── elf_parser.py    # ELF/DWARF parsing with enum & scaling detection
│   └── map_parser.py    # MAP file parser
├── generator/
│   └── a2l_generator.py # A2L file generation engine
├── utils/
│   ├── logger.py        # GUI logging utility
│   └── file_utils.py    # Path validation utilities
└── LICENSE              # Apache License 2.0
```

## 🔨 Building Executable & Creating Releases

### Automated Build System

The project includes an automated build script for creating releases:

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# 2. Run the build script
python build_executable.py
```

This creates:
- **dist/A2LGenerator.exe** - Standalone executable
- **releases/A2LGenerator-v*.zip** - Portable ZIP archive
- **releases/A2LGenerator-v*.tar.gz** - Compressed TAR archive
- **releases/RELEASE_NOTES_v*.md** - Release notes

### Manual Build

For custom builds:

```bash
pyinstaller --onefile --windowed \
  --add-data "config:config" \
  --add-data "parsers:parsers" \
  --add-data "generator:generator" \
  --add-data "utils:utils" \
  --collect-all ttkbootstrap \
  --collect-all elftools \
  main.py
```

### Release Management

Create releases on GitHub:

```bash
# Tag a release
git tag -a v2.1.0 -m "Release v2.1.0"

# Push tags to GitHub
git push origin --tags
```

**GitHub Actions** will automatically:
1. Build the executable on Windows
2. Create .zip and .tar.gz archives
3. Generate release notes
4. Create a GitHub release with downloads

### Version Scheme

- **vMAJOR.MINOR.PATCH** - Stable releases (current source version: **v2.1.0**)
- **vMAJOR.MINOR.PATCH-beta** - Beta pre-releases
- **vMAJOR.MINOR.PATCH-alpha** - Alpha pre-releases

Update `APP_VERSION` in `app_info.py` and this change history when preparing a new release. `VERSION` or `BUILD_VERSION` can override the release artifact version during a build.

## License

This project is licensed under the **Apache License 2.0** - see [LICENSE](LICENSE) file for details.

Apache License 2.0 is ideal for enterprise environments and provides:
- ✅ Commercial use, modification, and distribution
- ✅ **Patent protection** (explicit patent grant)
- ✅ **Liability protection** (clear disclaimer of warranties)
- ✅ Widely adopted in enterprises
- ✅ Professional standard for large-scale projects
- ⚠️ Requires: License and copyright notice

**Permissions**: Commercial Use | Modification | Distribution | Patent Use
**Conditions**: License & Copyright Notice | State Changes | Disclose Source
**Limitations**: Trademark Use | Warranty | Liability

## Contributing

Contributions are welcome! Please feel free to submit issues, fork the repository, and create pull requests.

## Support

For issues, feature requests, or questions, please open an issue on the GitHub repository.

## Disclaimer

This tool is provided as-is for A2L file generation from ELF and MAP files. Ensure generated A2L files are validated according to your specific compiler and automotive standards requirements.

## Author

**DevD** - Tool developer

---

**Version**: 2.1.0 | **Developer**: DevD | **Executable**: Previous releases available | **License**: Apache 2.0
