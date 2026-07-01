# A2L Generator

A modern, feature-rich GUI-based A2L (ASAP2) file generator for embedded automotive development. This tool extracts symbol information from ELF binaries and MAP files, automatically detects enums and floating-point scaling factors, and generates compliant A2L files for multiple compiler toolchains (GCC, IAR, ARMCC, TASKING, Hightec).

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

## Building Executable

To create a standalone executable (.exe):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

The resulting executable will:
- Not require Python installation
- Skip dependency checks (frozen app detection)
- Run directly on Windows systems

## License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) file for details.

MIT License is permissive and allows:
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use
- ⚠️ Requires: License and copyright notice

## Contributing

Contributions are welcome! Please feel free to submit issues, fork the repository, and create pull requests.

## Support

For issues, feature requests, or questions, please open an issue on the GitHub repository.

## Disclaimer

This tool is provided as-is for A2L file generation from ELF and MAP files. Ensure generated A2L files are validated according to your specific compiler and automotive standards requirements.

## Author

A2L Generator Contributors

---

**Status**: Production Ready | **Version**: 1.0.0 | **Python**: 3.7+ | **License**: MIT
