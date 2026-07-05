import re

def parse_map(map_file):
    """
    Parse MAP file to extract symbol addresses and sizes.
    Supports multiple compiler formats: GCC, IAR, TASKING, Hightec, ARMCC.
    Returns dict: {symbol_name: {"address": addr, "size": size}}
    """
    symbols = {}
    
    with open(map_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith(';') or line.startswith('#'):
            continue
        
        # Try multiple patterns for different compiler formats
        
        # Pattern 1: Hightec MAP: 0xADDRESS 0xSIZE SYMBOL
        match = re.match(r'^(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+(\w+)$', line)
        if match:
            addr, size, name = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": int(size, 16)
            }
            continue
        
        # Pattern 2: GCC/Generic: SYMBOL 0xADDRESS SIZE
        match = re.match(r'^(\w+)\s+(0x[0-9A-Fa-f]+)\s+(\d+)$', line)
        if match:
            name, addr, size = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": int(size)
            }
            continue
        
        # Pattern 3: TASKING/Hightec: SYMBOL ADDRESS SIZE (hex without 0x, 8-char format)
        match = re.match(r'^(\w+)\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})$', line)
        if match:
            name, addr, size = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": int(size, 16)
            }
            continue
        
        # Pattern 4: IAR: Symbol=SYMBOL Address=0xADDRESS Size=SIZE
        match = re.search(r'Symbol=(\w+)\s+Address=(0x[0-9A-Fa-f]+)\s+Size=(\d+)', line)
        if match:
            name, addr, size = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": int(size)
            }
            continue
        
        # Pattern 5: ARMCC: SYMBOL at 0xADDRESS size 0xSIZE
        match = re.search(r'(\w+)\s+at\s+(0x[0-9A-Fa-f]+)\s+size\s+(0x[0-9A-Fa-f]+)', line, re.IGNORECASE)
        if match:
            name, addr, size = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": int(size, 16)
            }
            continue
        
        # Pattern 6: Simple two-column: SYMBOL 0xADDRESS
        match = re.match(r'^(\w+)\s+(0x[0-9A-Fa-f]+)$', line)
        if match:
            name, addr = match.groups()
            symbols[name] = {
                "address": int(addr, 16),
                "size": 4  # Default size
            }
            continue
    
    return symbols
