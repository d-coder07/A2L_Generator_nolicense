import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from generator.a2l_generator import generate_a2l
from utils.resource_limits import MemorySnapshot, MIB


class TemplateUpdateTests(unittest.TestCase):
    def setUp(self):
        snapshot_patch = patch('utils.resource_limits.memory_snapshot', return_value=MemorySnapshot(
            16 * 1024 * MIB, 8 * 1024 * MIB, 100 * MIB, 10 * 1024 * MIB,
        ))
        snapshot_patch.start()
        self.addCleanup(snapshot_patch.stop)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.template_path = Path(self.directory.name) / 'template.a2l'
        self.output_path = Path(self.directory.name) / 'output.a2l'
        self.symbols = {
            'new_value': {'size': 1, 'address': 0x1234, 'datatype': 'UBYTE'},
            'other_value': {'size': 2, 'address': 0x2000, 'datatype': 'UWORD'},
        }
        self.template = (
            'ASAP2_VERSION 1 61\r\n'
            '/begin PROJECT Existing ""\r\n'
            '  /begin MODULE ExistingModule ""\r\n'
            '    /begin MEASUREMENT old_value "keep" UBYTE NO_COMPU_METHOD 0 0 0 255\r\n'
            '      ECU_ADDRESS 0x42\r\n'
            '    /end MEASUREMENT\r\n'
            '    /begin GROUP ExistingGroup "keep"\r\n'
            '    /end GROUP\r\n'
            '  /end MODULE\r\n'
            '/end PROJECT\r\n'
        )
        self.template_path.write_bytes(self.template.encode('utf-8'))

    def generate(self, **options):
        generate_a2l(self.symbols, {}, self.output_path, self.template_path, **options)
        return self.output_path.read_bytes().decode('utf-8')

    def test_automatic_generation_preserves_template_and_appends_variables(self):
        result = self.generate(only_update=True)
        prefix, suffix = self.template.split('  /end MODULE', 1)
        self.assertTrue(result.startswith(prefix))
        self.assertTrue(result.endswith('  /end MODULE' + suffix))
        for name in self.symbols:
            self.assertIn('/begin MEASUREMENT ' + name, result)
        self.assertGreater(result.index('/begin MEASUREMENT new_value'), result.index('/end GROUP'))
        self.assertNotIn('\n', result.replace('\r\n', ''))
        self.assertEqual(self.template_path.read_bytes(), self.template.encode('utf-8'))

    def test_manual_selection_only_appends_selected_variable_and_calibration(self):
        result = self.generate(selected_symbols={'new_value': 'rw'}, only_update=True)
        self.assertIn('/begin MEASUREMENT new_value', result)
        self.assertIn('/begin CHARACTERISTIC C_new_value', result)
        self.assertNotIn('other_value', result)
        self.assertIn('old_value', result)

    def test_repeated_generation_does_not_duplicate_definitions(self):
        result = self.generate(only_update=True, access='Read and Write')
        self.template_path.write_bytes(result.encode('utf-8'))
        self.assertEqual(self.generate(only_update=True, access='Read and Write'), result)

    def test_existing_variable_is_not_overwritten(self):
        self.symbols['old_value'] = {'size': 1, 'address': 0x9999, 'datatype': 'UBYTE'}
        result = self.generate(only_update=True)
        self.assertEqual(result.count('/begin MEASUREMENT old_value'), 1)
        self.assertIn('ECU_ADDRESS 0x42', result)
        self.assertNotIn('0x00009999', result)

    def test_empty_selection_keeps_template_identical(self):
        self.assertEqual(self.generate(selected_symbols=[], only_update=True), self.template)

    def test_default_mode_still_cleans_template(self):
        result = self.generate()
        self.assertNotIn('old_value', result)
        self.assertNotIn('ExistingGroup', result)
        self.assertIn('/begin MEASUREMENT new_value', result)


if __name__ == '__main__':
    unittest.main()
