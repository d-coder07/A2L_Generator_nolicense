from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import hashlib
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

# Toolchain/linker-generated symbols that are not application variables
_EXCLUDED_PREFIXES = ('__', '$', '.L', '_ZN', 'CSWTCH')

# Section indices that carry no addressable data
_NON_DATA_SHNDX = ('SHN_UNDEF', 'SHN_ABS', 'SHN_COMMON', 0)

# Bump when the parsing result layout changes so stale caches are ignored
_CACHE_VERSION = 9
_CACHE_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'A2LGenerator' / 'elf_cache'


def parse_elf(elf_file: str, use_cache: bool = True, jobs: int | None = None,
              expansion_mode: str = 'all') -> dict[str, Any]:
    """
    Parse ELF file to extract data symbols, types, enums, and scaling information.
    Only STT_OBJECT symbols are kept, so functions/API entry points never reach the A2L.
    File-local statics are included and de-duplicated by address.
    DWARF parsing is spread over CPU cores and the result is cached per ELF build.
    Returns dict: {a2l_name: {"address", "datatype", "size", "scaling", "enum", "symbol", "static"}}
    """
    if expansion_mode not in ('none', 'arrays', 'all'):
        raise ValueError(f'Unsupported aggregate expansion mode: {expansion_mode}')

    key = _cache_key(elf_file, expansion_mode)
    if use_cache:
        cached = _load_cache(key)
        if cached is not None:
            return cached

    enums, types_by_addr, types_by_name, aggregate_by_addr = _collect_dwarf_types(elf_file, jobs)
    symbols = _collect_symbols(elf_file, types_by_addr, types_by_name, aggregate_by_addr, expansion_mode)

    # Attach enum definitions
    symbols['_enums'] = enums

    if use_cache:
        _store_cache(key, symbols)
    return symbols


def _collect_symbols(elf_file: str, types_by_addr: dict[int, Any], types_by_name: dict[str, Any], aggregate_by_addr: dict[int, list[dict[str, Any]]], expansion_mode: str) -> dict[str, Any]:
    """Read the ELF symbol table and keep only addressable data objects."""
    symbols: dict[str, Any] = {}

    with open(elf_file, 'rb') as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name('.symtab')
        if not symtab:
            return symbols

        for symbol in symtab.iter_symbols():
            name = symbol.name
            if not name or name.startswith(_EXCLUDED_PREFIXES):
                continue
            # Functions, file and section entries would otherwise appear as measurement objects
            if symbol['st_info']['type'] != 'STT_OBJECT':
                continue
            if symbol['st_shndx'] in _NON_DATA_SHNDX:
                continue

            addr = symbol['st_value']
            size = symbol['st_size']
            if not addr or not size:
                continue

            # Address lookup resolves statics correctly even when the name is reused across files
            info = types_by_addr.get(addr) or types_by_name.get(name) or {}
            dtype = info.get('type') or _infer_type_from_size(size)

            # A2L cannot expose an aggregate as a scalar measurement. Expand its
            # addressable leaves and suppress the opaque root when expansion works.
            leaves = aggregate_by_addr.get(addr, []) if expansion_mode != 'none' else []
            if expansion_mode == 'arrays' and not info.get('is_array', False):
                leaves = []
            if leaves:
                for leaf in leaves:
                    leaf_name = leaf['name']
                    if leaf_name in symbols:
                        leaf_name = f'{leaf_name}__{leaf["address"]:08X}'
                    symbols[leaf_name] = {
                        "address": leaf['address'],
                        "datatype": leaf['datatype'],
                        "size": leaf['size'],
                        "scaling": 1.0,
                        "enum": leaf.get('enum'),
                        "symbol": leaf_name,
                        "static": symbol['st_info']['bind'] == 'STB_LOCAL',
                        "aggregate_root": name,
                    }
                    for field in ('bit_size', 'bit_offset', 'bit_mask'):
                        if field in leaf:
                            symbols[leaf_name][field] = leaf[field]
                continue

            key = name
            existing = symbols.get(key)
            if existing and existing['address'] != addr:
                key = f'{name}__{addr:08X}'

            symbols[key] = {
                "address": addr,
                "datatype": dtype,
                "size": size,
                "scaling": info.get('scaling', 1.0),
                "enum": info.get('enum'),
                "symbol": name,
                "static": symbol['st_info']['bind'] == 'STB_LOCAL',
            }

    return symbols


def _collect_dwarf_types(elf_file: str, jobs: int | None):
    """Parse DWARF type info, splitting the compilation units over worker processes."""
    workers = jobs if jobs else min(os.cpu_count() or 1, 8)

    if workers > 1:
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_dwarf_worker, [(elf_file, rank, workers) for rank in range(workers)]))
            return _merge_dwarf_results(results)
        except Exception:
            pass  # Fall back to in-process parsing when spawning is unavailable

    return _dwarf_worker((elf_file, 0, 1))


def _merge_dwarf_results(results):
    """Combine the per-worker DWARF dictionaries."""
    enums: dict[str, Any] = {}
    by_addr: dict[int, Any] = {}
    by_name: dict[str, Any] = {}
    aggregate_by_addr: dict[int, list[dict[str, Any]]] = {}
    for part_enums, part_addr, part_name, part_aggregates in results:
        enums.update(part_enums)
        by_addr.update(part_addr)
        for name, info in part_name.items():
            by_name.setdefault(name, info)
        for address, leaves in part_aggregates.items():
            aggregate_by_addr.setdefault(address, []).extend(leaves)
    return enums, by_addr, by_name, aggregate_by_addr


def _dwarf_worker(args: tuple[str, int, int]):
    """Worker entry point: parse every N-th compilation unit of the ELF file."""
    elf_file, rank, stride = args
    with open(elf_file, 'rb') as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            return {}, {}, {}, {}
        return _parse_dwarf_types(elf.get_dwarf_info(), rank, stride)


def _cache_key(elf_file: str, expansion_mode: str) -> str:
    """Identify a parse result by path, size and modification time."""
    stat = os.stat(elf_file)
    raw = f'{_CACHE_VERSION}|{expansion_mode}|{os.path.abspath(elf_file)}|{stat.st_size}|{stat.st_mtime_ns}'
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _load_cache(key: str) -> dict[str, Any] | None:
    path = _CACHE_DIR / f'{key}.pkl'
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def _store_cache(key: str, symbols: dict[str, Any]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_DIR / f'{key}.pkl', 'wb') as f:
            pickle.dump(symbols, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass


def _parse_dwarf_types(dwarf: Any, rank: int = 0, stride: int = 1) -> tuple[dict[str, Any], dict[int, dict[str, Any]], dict[str, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    """
    Extract enum definitions and variable type information from DWARF debug info.
    Only compilation units where index % stride == rank are processed.
    Returns: (enums, types_by_address, types_by_name, aggregate_leaves_by_address)
    """
    enums: dict[str, Any] = {}
    by_addr: dict[int, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    aggregate_by_addr: dict[int, list[dict[str, Any]]] = {}

    for index, CU in enumerate(dwarf.iter_CUs()):
        if index % stride != rank:
            continue
        addr_size = CU['address_size']
        for die in CU.iter_DIEs():
            # Extract enum types
            if die.tag == 'DW_TAG_enumeration_type':
                enum_name = _die_name(die)
                if enum_name:
                    enum_values = {}
                    for child in die.iter_children():
                        if child.tag == 'DW_TAG_enumerator':
                            const_name = _die_name(child)
                            const_value = child.attributes.get('DW_AT_const_value')
                            if const_name and const_value is not None:
                                enum_values[const_name] = const_value.value
                    enums[enum_name] = enum_values

            # Extract variable type and scaling info
            elif die.tag == 'DW_TAG_variable':
                var_name = _die_name(die)
                if not var_name:
                    continue

                type_die = _resolve_type(die)
                if type_die is None:
                    continue

                info: dict[str, Any] = {}
                type_name = _get_type_name(type_die)
                if type_name:
                    info['type'] = type_name
                info['is_array'] = _strip_type(type_die).tag == 'DW_TAG_array_type'

                scaling = _extract_scaling(die)
                if scaling:
                    info['scaling'] = scaling

                enum_ref = _get_enum_reference(_strip_type(type_die))
                if enum_ref:
                    info['enum'] = enum_ref

                static_addr = _static_address(die, addr_size)
                if info:
                    by_name.setdefault(var_name, info)
                if static_addr is not None:
                    leaves = _expand_aggregate(type_die, var_name, static_addr)
                    if leaves:
                        aggregate_by_addr[static_addr] = leaves
                    if info:
                        by_addr[static_addr] = info

    return enums, by_addr, by_name, aggregate_by_addr


def _die_name(die: Any) -> str | None:
    """Return the DW_AT_name of a DIE as text."""
    attr = die.attributes.get('DW_AT_name')
    if not attr:
        return None
    return attr.value.decode('utf-8') if isinstance(attr.value, bytes) else str(attr.value)


def _static_address(die: Any, addr_size: int) -> int | None:
    """Return the absolute address of a variable whose location is a plain DW_OP_addr."""
    loc = die.attributes.get('DW_AT_location')
    if not loc or not isinstance(loc.value, (list, bytes, bytearray)):
        return None
    expr = bytes(loc.value)
    if len(expr) < 1 + addr_size or expr[0] != 0x03:  # DW_OP_addr
        return None
    return int.from_bytes(expr[1:1 + addr_size], 'little')


def _resolve_type(die: Any) -> Any:
    """Dereference DW_AT_type to get the actual type DIE."""
    if 'DW_AT_type' not in die.attributes:
        return None
    try:
        return die.get_DIE_from_attribute('DW_AT_type')
    except Exception:
        return None


def _expand_aggregate(type_die: Any, root_name: str, root_address: int) -> list[dict[str, Any]]:
    """Expand an aggregate variable into leaf names with absolute addresses."""
    leaves: list[dict[str, Any]] = []
    _walk_aggregate(_strip_type(type_die), root_name, root_address, leaves, set(), 0)
    return leaves


def _walk_aggregate(type_die: Any, name: str, address: int, leaves: list[dict[str, Any]],
                    active_types: set[int], depth: int) -> None:
    """Recursively calculate array strides and member offsets from DWARF DIEs."""
    if type_die is None or depth > 32:
        return
    type_die = _strip_type(type_die)
    if type_die is None:
        return

    # Protect against self-referential structures such as linked-list nodes.
    die_id = getattr(type_die, 'offset', id(type_die))
    if die_id in active_types:
        return

    if type_die.tag == 'DW_TAG_array_type':
        element_type = _resolve_type(type_die)
        element_type = _strip_type(element_type)
        element_size = _type_size(element_type)
        count = _array_count(type_die)
        if element_type is None or element_size <= 0 or count <= 0:
            return
        for index in range(count):
            element_name = f'{name}[{index}]'
            if _is_aggregate(element_type):
                _walk_aggregate(element_type, element_name, address + index * element_size,
                                leaves, active_types | {die_id}, depth + 1)
            else:
                _append_leaf(leaves, element_name, element_type, address + index * element_size)
        return

    if type_die.tag in ('DW_TAG_structure_type', 'DW_TAG_union_type', 'DW_TAG_class_type'):
        is_union = type_die.tag == 'DW_TAG_union_type'
        members = [child for child in type_die.iter_children() if child.tag == 'DW_TAG_member']
        for member in members:
            member_name = _die_name(member)
            member_type = _strip_type(_resolve_type(member))
            if not member_name or member_type is None:
                continue
            member_address = address if is_union else address + _member_offset(member)
            qualified_name = f'{name}.{member_name}'
            bit_info = _member_bit_info(member, member_type)
            if bit_info:
                member_address += bit_info.pop('byte_offset', 0)
            if _is_aggregate(member_type):
                _walk_aggregate(member_type, qualified_name, member_address,
                                leaves, active_types | {die_id}, depth + 1)
            else:
                _append_leaf(leaves, qualified_name, member_type, member_address, bit_info)


def _append_leaf(leaves: list[dict[str, Any]], name: str, type_die: Any, address: int,
                 bit_info: dict[str, int] | None = None) -> None:
    """Append a scalar DWARF leaf when its representation is supported by A2L."""
    datatype = _get_type_name(type_die)
    size = _type_size(type_die)
    if datatype and size > 0:
        leaf = {
            'name': name,
            'address': address,
            'datatype': datatype,
            'size': size,
            'enum': _get_enum_reference(type_die),
        }
        if bit_info:
            leaf.update(bit_info)
        leaves.append(leaf)


def _member_bit_info(member_die: Any, member_type: Any) -> dict[str, int] | None:
    """Return bit-field width and mask, using DWARF's modern or legacy attributes."""
    bit_size = _attribute_int(member_die, 'DW_AT_bit_size', 'DW_AT_bit_length')
    if bit_size is None:
        return None

    container_size = _type_size(member_type)
    container_bits = container_size * 8
    if bit_size <= 0 or container_bits <= 0 or bit_size > container_bits:
        return None

    absolute_bit_offset = _attribute_int(member_die, 'DW_AT_data_bit_offset')
    if absolute_bit_offset is not None:
        byte_offset, bit_offset = divmod(absolute_bit_offset, 8)
    else:
        bit_offset_value = _attribute_int(member_die, 'DW_AT_bit_offset')
        if bit_offset_value is None:
            return None
        # Legacy DWARF bit_offset counts from the most-significant bit.
        byte_offset = 0
        bit_offset = container_bits - bit_offset_value - bit_size

    if bit_offset < 0 or bit_offset + bit_size > container_bits:
        return None

    return {
        'byte_offset': byte_offset,
        'bit_size': bit_size,
        'bit_offset': bit_offset,
        'bit_mask': ((1 << bit_size) - 1) << bit_offset,
    }


def _attribute_int(die: Any, *names: str) -> int | None:
    """Read an integer DWARF attribute, accepting pyelftools value wrappers."""
    for name in names:
        attribute = die.attributes.get(name)
        if attribute is None:
            continue
        value = getattr(attribute, 'value', attribute)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _is_aggregate(type_die: Any) -> bool:
    """Return whether a DIE must be recursively expanded."""
    return type_die is not None and type_die.tag in (
        'DW_TAG_array_type', 'DW_TAG_structure_type', 'DW_TAG_union_type', 'DW_TAG_class_type'
    )


def _type_size(type_die: Any) -> int:
    """Read DW_AT_byte_size from a type DIE, following arrays and qualifiers."""
    type_die = _strip_type(type_die)
    if type_die is None:
        return 0
    byte_size = type_die.attributes.get('DW_AT_byte_size')
    if byte_size:
        return int(byte_size.value)
    if type_die.tag == 'DW_TAG_pointer_type':
        return int(type_die.attributes.get('DW_AT_byte_size', type('Value', (), {'value': 4})()).value)
    return 0


def _array_count(array_die: Any) -> int:
    """Return the first DWARF array dimension count."""
    for child in array_die.iter_children():
        if child.tag != 'DW_TAG_subrange_type':
            continue
        count = child.attributes.get('DW_AT_count')
        if count:
            return max(0, int(count.value))
        upper = child.attributes.get('DW_AT_upper_bound')
        if upper:
            return max(0, int(upper.value) + 1)
    return 0


def _member_offset(member_die: Any) -> int:
    """Read a constant DWARF member offset from common expression encodings."""
    location = member_die.attributes.get('DW_AT_data_member_location')
    if not location:
        return 0
    value = location.value
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray, list)):
        expression = bytes(value)
        if not expression:
            return 0

        # DW_OP_plus_uconst <ULEB128>
        if expression[0] == 0x23:
            return _decode_uleb128(expression, 1)

        # DW_OP_constu <ULEB128>, used by some HighTec/TASKING DWARF producers.
        if expression[0] == 0x10:
            return _decode_uleb128(expression, 1)

        # DW_OP_const1u/const2u/const4u/const8u.
        const_widths = {0x08: 1, 0x09: 2, 0x0A: 4, 0x0B: 8}
        if expression[0] in const_widths:
            width = const_widths[expression[0]]
            if len(expression) >= width + 1:
                return int.from_bytes(expression[1:width + 1], 'little')

        # DW_OP_lit0 ... DW_OP_lit31 encode small offsets directly in the opcode.
        if 0x30 <= expression[0] <= 0x4F:
            return expression[0] - 0x30
    return 0


def _decode_uleb128(data: bytes, start: int) -> int:
    """Decode an unsigned LEB128 value from a DWARF expression."""
    result = 0
    shift = 0
    for byte in data[start:]:
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result
        shift += 7
    return 0


# DWARF DW_AT_encoding integer constants (DWARF v4 spec, section 7.8)
_DW_ATE_BOOL = 0x02
_DW_ATE_FLOAT = 0x04
_DW_ATE_SIGNED = 0x05
_DW_ATE_SIGNED_CHAR = 0x06
_DW_ATE_UNSIGNED = 0x07
_DW_ATE_UNSIGNED_CHAR = 0x08


def _infer_type_from_size(size: int) -> str:
    """Infer A2L datatype from symbol size in bytes when no DWARF info is available."""
    if size == 2:
        return "UWORD"
    if size == 4:
        return "ULONG"
    # Aggregates of unknown layout are exposed as byte arrays
    return "UBYTE"


# Qualifiers that do not change the underlying representation
_TRANSPARENT_TAGS = ('DW_TAG_typedef', 'DW_TAG_const_type', 'DW_TAG_volatile_type', 'DW_TAG_restrict_type')


def _strip_type(type_die: Any) -> Any:
    """Follow typedef/const/volatile chains down to the representing type DIE."""
    depth = 0
    while type_die is not None and type_die.tag in _TRANSPARENT_TAGS and depth < 16:
        type_die = _resolve_type(type_die)
        depth += 1
    return type_die


def _get_type_name(type_die: Any) -> str | None:
    """Extract the base type name from a DWARF type DIE, or None when not representable."""
    type_die = _strip_type(type_die)
    if not type_die:
        return None

    if type_die.tag == 'DW_TAG_base_type':
        encoding = type_die.attributes.get('DW_AT_encoding')
        byte_size = type_die.attributes.get('DW_AT_byte_size')

        if encoding and byte_size:
            size = byte_size.value
            # pyelftools returns DW_AT_encoding as integer, not string
            enc_val = encoding.value

            if enc_val == _DW_ATE_FLOAT:
                if size == 4:
                    return "FLOAT32_IEEE"
                elif size == 8:
                    return "FLOAT64_IEEE"
            elif enc_val == _DW_ATE_SIGNED:
                if size == 1:
                    return "BYTE"
                elif size == 2:
                    return "WORD"
                elif size == 4:
                    return "LONG"
            elif enc_val in (_DW_ATE_UNSIGNED, _DW_ATE_BOOL, _DW_ATE_UNSIGNED_CHAR):
                if size == 1:
                    return "UBYTE"
                elif size == 2:
                    return "UWORD"
                elif size == 4:
                    return "ULONG"
            elif enc_val == _DW_ATE_SIGNED_CHAR:
                return "BYTE"

    elif type_die.tag == 'DW_TAG_enumeration_type':
        byte_size = type_die.attributes.get('DW_AT_byte_size')
        size = byte_size.value if byte_size else 4
        return {1: "UBYTE", 2: "UWORD"}.get(size, "ULONG")

    elif type_die.tag == 'DW_TAG_array_type':
        # The element type drives the A2L datatype; the count comes from the symbol size
        return _get_type_name(_resolve_type(type_die))

    elif type_die.tag == 'DW_TAG_pointer_type':
        return "ULONG"

    return None


def _get_enum_reference(type_die: Any) -> str | None:
    """Check if type_die references an enumeration type."""
    if type_die is not None and type_die.tag == 'DW_TAG_enumeration_type':
        return _die_name(type_die)
    return None


def _extract_scaling(die: Any) -> float | None:
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



