import re

def parse_map(map_file):
    """
    Parse MAP file to extract symbol addresses and sizes.
    Returns dict: {symbol_name: {"address": addr, "size": size}}
    """
    symbols = {}
    with open(map_file, 'r') as f:
        for line in f:
            match = re.match(r'(\w+)\s+0x([0-9A-F]+)\s+(\d+)', line)
            if match:
                name, addr, size = match.groups()
                symbols[name] = {
                    "address": int(addr, 16),
                    "size": int(size)
                }
    return symbols
