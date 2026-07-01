# A2L Generator

A modern, feature-rich GUI-based A2L (ASAP2) file generator for embedded automotive development. This tool extracts symbol information from ELF binaries and MAP files, automatically detects enums and floating-point scaling factors, and generates compliant A2L files for multiple compiler toolchains (GCC, IAR, ARMCC, TASKING, Hightec).

## 📥 Downloads & Releases

Get the latest standalone executable without needing Python installed:

| Release | Format | Size | Download |
|---------|--------|------|----------|
| **v1.0.0 (Latest)** | Windows .exe | 20.6 MB | [Download](#) |
| | ZIP Archive | 20.4 MB | [Download](#) |
| | TAR.GZ Archive | 20.4 MB | [Download](#) |

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
- **Automatic Dependency Management**: Auto-installs required packages on first run
- **Advanced ELF Parsing**:
  - DWARF debug symbol extraction
  - Automatic enum type detection
  - Floating-point scaling factor detection
  - Comprehensive type mapping (signed/unsigned integers, IEEE floats)
- **Multi-Format Support**: Classic A2L, Extended A2L, AUTOSAR A2L
- **File Management**: Add/remove ELF and MAP files with session history
- **Real-Time Logging**: Activity log shows generation progress and results
- **Compiler Support**: GCC, IAR, ARMCC, TASKING, Hightec
- **Cross-Platform**: Works on Windows with Python 3.7+

## Requirements

- Python 3.7 or higher
- Required packages (auto-installed):
  - `pyelftools` - ELF binary parsing with DWARF support
  - `ttkbootstrap` - Modern themed Tkinter widgets

## Installation

1. Clone the repository:
```bash
git clone https://github.com/d-coder07/A2L_Generator_nolicense.git
cd A2L_Generator
```

2. Run the application:
```bash
python main.py
```

Dependencies will be automatically installed on first run.

## Usage

1. **Launch the App**: `python main.py`
2. **Add Source Files**:
   - Click "Add ELF" to select an ELF binary
   - Click "Add MAP" to select a MAP file
3. **Configure Generation**:
   - Select compiler from the dropdown
   - Choose output A2L format (Classic/Extended/AUTOSAR)
   - Specify output file path
4. **Generate A2L**: Click "Generate A2L"
5. **View Results**: Check the Activity Log for progress and status
6. **Open Output**: Click "Open Folder" to view generated A2L file

## Project Structure

```
A2L_Generator/
├── main.py              # Entry point with dependency checking
├── gui.py               # Modern Windows 11 UI implementation
├── config/
│   ├── compilers.json   # Supported compiler options
│   └── history.json     # Session history
├── parsers/
│   ├── elf_parser.py    # ELF/DWARF parsing with enum & scaling detection
│   ├── map_parser.py    # MAP file parser
│   └── metadata_parser.py # Metadata extraction (CSV/Excel)
├── generator/
│   └── a2l_generator.py # A2L file generation engine
├── utils/
│   ├── logger.py        # GUI logging utility
│   └── file_utils.py    # Path validation utilities
└── LICENSE              # MIT License
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
git tag -a v1.0.0 -m "Release v1.0.0"

# Push tags to GitHub
git push origin --tags
```

**GitHub Actions** will automatically:
1. Build the executable on Windows
2. Create .zip and .tar.gz archives
3. Generate release notes
4. Create a GitHub release with downloads

### Version Scheme

- **v1.x.x** - Stable releases
- **v1.x.x-beta** - Beta pre-releases
- **v1.x.x-alpha** - Alpha pre-releases

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

A2L Generator Contributors

---

**Status**: Production Ready | **Version**: 1.0.0 | **Executable**: Available | **License**: Apache 2.0
