from elftools.elf.elffile import ELFFile

def parse_elf(elf_file):
    """
    Parse ELF file to extract symbols, types, enums, and scaling information.
    Uses DWARF debug info when available.
    Returns dict: {symbol_name: {"address": addr, "datatype": type, "scaling": scale, "enum": enum_name, "size": size}}
    """
    symbols = {}
    enums = {}
    dwarf_types = {}

    with open(elf_file, 'rb') as f:
        elf = ELFFile(f)

        # Extract DWARF information if available
        if elf.has_dwarf_info():
            dwarf = elf.get_dwarf_info()
            enums, dwarf_types = _parse_dwarf_types(dwarf)

        # Extract symbol table
        symtab = elf.get_section_by_name('.symtab')
        if not symtab:
            return symbols

        for symbol in symtab.iter_symbols():
            name = symbol.name
            if not name:
                continue

            addr = symbol['st_value']
            size = symbol['st_size']

            # Try to get type info from DWARF
            dwarf_type = dwarf_types.get(name, {})
            dtype = dwarf_type.get('type', _infer_type_from_size(size))
            scaling = dwarf_type.get('scaling', 1.0)
            enum_ref = dwarf_type.get('enum', None)

            symbols[name] = {
                "address": addr,
                "datatype": dtype,
                "size": size,
                "scaling": scaling,
                "enum": enum_ref
            }

    # Attach enum definitions
    symbols['_enums'] = enums
    return symbols


def _parse_dwarf_types(dwarf):
    """
    Extract enum definitions and variable type information from DWARF debug info.
    Returns: (enums_dict, dwarf_types_dict)
    """
    enums = {}
    dwarf_types = {}

    for CU in dwarf.iter_CUs():
        for die in CU.iter_DIEs():
            # Extract enum types
            if die.tag == 'DW_TAG_enumeration_type':
                enum_name = die.attributes.get('DW_AT_name')
                if enum_name:
                    enum_name = enum_name.value.decode('utf-8') if isinstance(enum_name.value, bytes) else enum_name.value
                    enum_values = {}
                    for child in die.iter_children():
                        if child.tag == 'DW_TAG_enumerator':
                            const_name = child.attributes.get('DW_AT_name')
                            const_value = child.attributes.get('DW_AT_const_value')
                            if const_name and const_value:
                                const_name_str = const_name.value.decode('utf-8') if isinstance(const_name.value, bytes) else const_name.value
                                enum_values[const_name_str] = const_value.value
                    enums[enum_name] = enum_values

            # Extract variable type and scaling info
            elif die.tag == 'DW_TAG_variable':
                var_name = die.attributes.get('DW_AT_name')
                if var_name:
                    var_name_str = var_name.value.decode('utf-8') if isinstance(var_name.value, bytes) else var_name.value
                    
                    type_info = {}
                    type_die = _get_type_die(die, dwarf)
                    if type_die:
                        type_info['type'] = _get_type_name(type_die)
                        
                        # Look for scaling factors in location or other attributes
                        scaling = _extract_scaling(die)
                        if scaling:
                            type_info['scaling'] = scaling
                        
                        # Check if variable references an enum
                        enum_ref = _get_enum_reference(type_die)
                        if enum_ref:
                            type_info['enum'] = enum_ref
                    
                    if type_info:
                        dwarf_types[var_name_str] = type_info

    return enums, dwarf_types


def _get_type_die(die, dwarf):
    """Dereference DW_AT_type to get the actual type DIE."""
    type_attr = die.attributes.get('DW_AT_type')
    if type_attr:
        try:
            return dwarf.get_DIE_from_refaddr(type_attr.value)
        except:
            pass
    return None


def _get_type_name(type_die):
    """Extract the base type name from a DWARF type DIE."""
    if not type_die:
        return "UBYTE"

    if type_die.tag == 'DW_TAG_base_type':
        encoding = type_die.attributes.get('DW_AT_encoding')
        byte_size = type_die.attributes.get('DW_AT_byte_size')

        if encoding and byte_size:
            size = byte_size.value
            enc_name = encoding.value

            # Map DWARF encoding to A2L types
            if enc_name == 'DW_ATE_float':
                if size == 4:
                    return "FLOAT32_IEEE"
                elif size == 8:
                    return "FLOAT64_IEEE"
            elif enc_name == 'DW_ATE_signed':
                if size == 1:
                    return "BYTE"
                elif size == 2:
                    return "WORD"
                elif size == 4:
                    return "LONG"
            elif enc_name == 'DW_ATE_unsigned':
                if size == 1:
                    return "UBYTE"
                elif size == 2:
                    return "UWORD"
                elif size == 4:
                    return "ULONG"

    elif type_die.tag == 'DW_TAG_enumeration_type':
        enum_name = type_die.attributes.get('DW_AT_name')
        if enum_name:
            return enum_name.value.decode('utf-8') if isinstance(enum_name.value, bytes) else enum_name.value

    elif type_die.tag in ('DW_TAG_pointer_type', 'DW_TAG_const_type', 'DW_TAG_volatile_type'):
        # Dereference and try again
        type_attr = type_die.attributes.get('DW_AT_type')
        if type_attr:
            try:
                return _get_type_name(type_die.dwarfinfo.get_DIE_from_refaddr(type_attr.value))
            except:
                pass

    return "UBYTE"


def _get_enum_reference(type_die):
    """Check if type_die references an enumeration type."""
    if type_die and type_die.tag == 'DW_TAG_enumeration_type':
        enum_name = type_die.attributes.get('DW_AT_name')
        if enum_name:
            return enum_name.value.decode('utf-8') if isinstance(enum_name.value, bytes) else enum_name.value
    return None


def _extract_scaling(die):
    """
    Attempt to extract scaling information from variable attributes.
    Looks for metadata in DW_AT_location or custom attributes.
    Returns scaling factor or None.
    """
    # Look for scaling in variable name suffix (e.g., "temperature_scale_10" -> 10)
    var_name = die.attributes.get('DW_AT_name')
    if var_name:
        name_str = var_name.value.decode('utf-8') if isinstance(var_name.value, bytes) else var_name.value
        if '_scale_' in name_str or '_scaling_' in name_str:
            try:
                parts = name_str.split('_')
                for i, part in enumerate(parts):
                    if part in ('scale', 'scaling') and i + 1 < len(parts):
                        return float(parts[i + 1])
            except:
                pass
    return None


def _infer_type_from_size(size):
    """Fallback type inference based on symbol size."""
    if size == 1:
        return "UBYTE"
    elif size == 2:
        return "UWORD"
    elif size == 4:
        return "ULONG"
    elif size == 8:
        return "FLOAT64_IEEE"
    else:
        return "UBYTE"
