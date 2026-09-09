import re

# Linker-defined symbols to exclude (not ECU variables)
_LINKER_SYMBOL_PREFIXES = ('__', '$', '$$')

# Matches valid C symbol names, TASKING array indices (var[0]) and struct members (var.member)
_SYM = r'[A-Za-z_][\w\[\]\.]*'


def parse_map(map_file):
    """
    Parse MAP file to extract symbol addresses and sizes.
    Supports: GNU LD (Hightec/GCC), TASKING lc_tc, IAR, ARMCC.
    Returns dict: {symbol_name: {"address": addr, "size": size}}
    """
    symbols = {}

    with open(map_file, 'r', encoding='utf-8', errors='ignore') as f:
        raw_lines = f.readlines()

    for raw_line in raw_lines:
        # TASKING lc_tc wraps table rows in | borders — remove them
        if '|' in raw_line:
            raw_line = raw_line.replace('|', ' ')

        line = raw_line.strip()
        if not line:
            continue
        # Skip comment lines and table-border/decoration lines
        if line[0] in (';', '#', '+', '=', '*', '/', '-'):
            continue

        # ------------------------------------------------------------------
        # Pattern 1: explicit 0xADDRESS 0xSIZE SYMBOL  (Hightec direct)
        # ------------------------------------------------------------------
        m = re.match(r'^(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+(' + _SYM + r')\s*$', line)
        if m:
            addr, size, name = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols[name] = {"address": int(addr, 16), "size": int(size, 16)}
            continue

        # ------------------------------------------------------------------
        # Pattern 7: GNU LD stripped-indent line: 0xADDR  SYMBOL
        # After strip() the leading whitespace is gone, leaving one hex + identifier
        # ------------------------------------------------------------------
        m = re.match(r'^(0x[0-9A-Fa-f]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', line)
        if m:
            addr, name = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols.setdefault(name, {"address": int(addr, 16), "size": 0})
            continue

        # ------------------------------------------------------------------
        # Pattern 4: IAR keyword format: Symbol=NAME Address=0xADDR Size=N
        # ------------------------------------------------------------------
        m = re.search(r'Symbol=(\w+)\s+Address=(0x[0-9A-Fa-f]+)\s+Size=(\d+)', line)
        if m:
            name, addr, size = m.groups()
            symbols[name] = {"address": int(addr, 16), "size": int(size)}
            continue

        # ------------------------------------------------------------------
        # Pattern 5: ARMCC: SYMBOL at 0xADDRESS size 0xSIZE
        # ------------------------------------------------------------------
        m = re.search(r'(' + _SYM + r')\s+at\s+(0x[0-9A-Fa-f]+)\s+size\s+(0x[0-9A-Fa-f]+)',
                      line, re.IGNORECASE)
        if m:
            name, addr, size = m.groups()
            symbols[name] = {"address": int(addr, 16), "size": int(size, 16)}
            continue

        # ------------------------------------------------------------------
        # Pattern 8: TASKING symbol table:
        #   SYMBOL  .section  space  ADDR8
        # (| already removed; line ends after 6-8 hex address)
        # ------------------------------------------------------------------
        m = re.match(r'^(' + _SYM + r')\s+\.\w+\s+\w+\s+([0-9A-Fa-f]{6,8})\s*$', line)
        if m:
            name, addr = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols.setdefault(name, {"address": int(addr, 16), "size": 0})
            continue

        # ------------------------------------------------------------------
        # Pattern 9: TASKING located objects:
        #   SYMBOL  .section  space  FROM8  TO8  type
        # Size = TO - FROM + 1
        # ------------------------------------------------------------------
        m = re.match(r'^(' + _SYM + r')\s+\.\w+\s+\w+\s+([0-9A-Fa-f]{6,8})\s+([0-9A-Fa-f]{6,8})\s+\w+',
                     line)
        if m:
            name, from_addr, to_addr = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                size = int(to_addr, 16) - int(from_addr, 16) + 1
                symbols.setdefault(name, {"address": int(from_addr, 16), "size": size})
            continue

        # ------------------------------------------------------------------
        # Pattern 2: GCC generic: SYMBOL 0xADDRESS  decimal_SIZE
        # ------------------------------------------------------------------
        m = re.match(r'^(' + _SYM + r')\s+(0x[0-9A-Fa-f]+)\s+(\d+)\s*$', line)
        if m:
            name, addr, size = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols[name] = {"address": int(addr, 16), "size": int(size)}
            continue

        # ------------------------------------------------------------------
        # Pattern 3: TASKING/Hightec bare hex: SYMBOL ADDR6-8 SIZE1-8 [extra]
        # Requires name to start with letter/underscore to avoid hex-addr
        # mis-classification.
        # ------------------------------------------------------------------
        m = re.match(r'^([A-Za-z_][\w\[\]\.]*)'  # symbol name
                     r'\s+([0-9A-Fa-f]{6,8})'    # 6-8 hex address (no 0x)
                     r'\s+([0-9A-Fa-f]{1,8})'    # 1-8 hex size
                     r'(?:\s|$)', line)
        if m:
            name, addr, size = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols.setdefault(name, {"address": int(addr, 16), "size": int(size, 16)})
            continue

        # ------------------------------------------------------------------
        # Pattern 6: minimal two-column: SYMBOL 0xADDRESS
        # ------------------------------------------------------------------
        m = re.match(r'^(' + _SYM + r')\s+(0x[0-9A-Fa-f]+)\s*$', line)
        if m:
            name, addr = m.groups()
            if not any(name.startswith(p) for p in _LINKER_SYMBOL_PREFIXES):
                symbols.setdefault(name, {"address": int(addr, 16), "size": 4})
            continue

    return symbols
