"""Builds A2L file from parsed data."""


def generate_a2l(elf_data, map_data, metadata, output_path):
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write('# A2L output placeholder\n')
        output_file.write(f'ELF data: {elf_data}\n')
        output_file.write(f'MAP data: {map_data}\n')
        output_file.write(f'Metadata: {metadata}\n')
