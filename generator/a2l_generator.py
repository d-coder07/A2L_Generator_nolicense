"""Builds A2L file from parsed ELF and MAP data."""

import os


def generate_a2l(elf_data, map_data, output_path, template_path=None, selected_symbols=None, advanced_mode=False):
    selected_symbols = selected_symbols if selected_symbols is not None else sorted(map_data.keys())
    selected_symbols = [symbol for symbol in selected_symbols if symbol in map_data]

    body_lines = []
    body_lines.append('/begin PROJECT A2LGenerator "A2L Generator Project"')
    body_lines.append('  /begin MODULE A2LModule "Generated from ELF and MAP"')
    body_lines.append('    /begin CHARACTERISTIC A2L_Export "Generated A2L characteristics"')
    body_lines.append('      DESCRIPTION \'Generated A2L from ELF and MAP input\'')
    body_lines.append('      LONG 0')
    body_lines.append('    /end CHARACTERISTIC')

    body_lines.append('    /begin MEASUREMENT A2L_MapSymbols "Parsed MAP symbols"')
    for symbol in sorted(selected_symbols):
        data = map_data.get(symbol, {})
        address = data.get('address', 0)
        size = data.get('size', 0)
        body_lines.append(f'      /begin VALUE {symbol} {address} {size} /end VALUE')
    body_lines.append('    /end MEASUREMENT')

    body_lines.append('    /begin MEASUREMENT A2L_ElfSymbols "Parsed ELF symbols"')
    for symbol in sorted(selected_symbols):
        data = elf_data.get(symbol, {})
        address = data.get('address', 0)
        size = data.get('size', 0)
        dtype = data.get('datatype', 'UNKNOWN')
        body_lines.append(f'      /begin VALUE {symbol} {address} {size} /end VALUE  # {dtype}')
    body_lines.append('    /end MEASUREMENT')

    if advanced_mode:
        compu_lines = _build_compu_method_sections(elf_data, selected_symbols)
        body_lines.extend(compu_lines)

    body_lines.append('  /end MODULE')
    body_lines.append('/end PROJECT')

    body_text = '\n'.join(body_lines) + '\n'

    if template_path and os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as template_file:
            template_text = template_file.read()

        if '{{A2L_BODY}}' in template_text:
            final_text = template_text.replace('{{A2L_BODY}}', body_text)
        elif '# INSERT A2L HERE' in template_text:
            final_text = template_text.replace('# INSERT A2L HERE', body_text)
        else:
            final_text = template_text.rstrip() + '\n\n' + body_text
    else:
        final_text = body_text

    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(final_text)


def _build_compu_method_sections(elf_data, selected_symbols):
    sections = []
    for symbol in selected_symbols:
        symbol_data = elf_data.get(symbol)
        if not symbol_data:
            continue

        dtype = symbol_data.get('datatype', 'UNKNOWN')
        scaling = symbol_data.get('scaling', 1.0)
        method_name = f'CM_{symbol}'
        sections.append(f'    /begin COMPU_METHOD {method_name} "Auto-generated compu method for {symbol}"')
        sections.append(f'      DATATYPE {dtype}')
        sections.append(f'      FORMAT "{dtype}"')
        if scaling and scaling != 1.0:
            sections.append(f'      FACTOR {scaling}')
        sections.append('    /end COMPU_METHOD')
    return sections
