import unittest
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from generator.a2l_generator import generate_a2l
from parsers import elf_parser
from utils import resource_limits


class ResourceProtectionTests(unittest.TestCase):
    def setUp(self):
        self.safe = resource_limits.MemorySnapshot(
            16 * 1024 * resource_limits.MIB, 8 * 1024 * resource_limits.MIB,
            100 * resource_limits.MIB, 10 * 1024 * resource_limits.MIB,
        )
        self.snapshot_patch = patch.object(resource_limits, 'memory_snapshot', return_value=self.safe)
        self.snapshot_patch.start()
        self.addCleanup(self.snapshot_patch.stop)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.elf_path = Path(self.directory.name) / 'input.elf'
        self.elf_path.write_bytes(b'test fixture')

    def test_physical_commit_and_process_limits_stop_work(self):
        snapshots = [
            resource_limits.MemorySnapshot(self.safe.total, 512 * resource_limits.MIB, self.safe.process),
            resource_limits.MemorySnapshot(self.safe.total, self.safe.available, self.safe.process, 128 * resource_limits.MIB),
            resource_limits.MemorySnapshot(self.safe.total, self.safe.available, 600 * resource_limits.MIB),
        ]
        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot):
                guard = resource_limits.ResourceGuard(512)
                with patch.object(resource_limits, 'memory_snapshot', return_value=snapshot):
                    with self.assertRaises(resource_limits.ResourceLimitError):
                        guard.check(force=True)

    def test_preflight_checks_projected_allocations(self):
        guard = resource_limits.ResourceGuard(512)
        with self.assertRaises(resource_limits.ResourceLimitError):
            guard.check(additional_bytes=500 * resource_limits.MIB, force=True)
        with self.assertRaises(ValueError):
            resource_limits.ResourceGuard(128)

    def test_error_explains_the_specific_projection_that_triggered(self):
        snapshot = resource_limits.MemorySnapshot(
            32 * 1024 * resource_limits.MIB, 9190 * resource_limits.MIB,
            2489 * resource_limits.MIB, 8192 * resource_limits.MIB,
        )
        guard = resource_limits.ResourceGuard(4096)
        with patch.object(resource_limits, 'memory_snapshot', return_value=snapshot):
            with self.assertRaises(resource_limits.ResourceLimitError) as caught:
                guard.check(additional_bytes=1800 * resource_limits.MIB, force=True,
                            context='preparing the output file')
        message = str(caught.exception)
        self.assertIn('during preparing the output file', message)
        self.assertIn('Current process memory: 2489 MiB', message)
        self.assertIn('projected: 4289 MiB / 4096 MiB budget', message)
        self.assertIn('Protection triggered by: process memory budget', message)
        self.assertIn('projected headroom: 7390 MiB', message)

    def test_screenshot_memory_readings_allow_work_within_budget(self):
        snapshot = resource_limits.MemorySnapshot(
            64 * 1024 * resource_limits.MIB, 9190 * resource_limits.MIB,
            2489 * resource_limits.MIB, 8192 * resource_limits.MIB,
        )
        with patch.object(resource_limits, 'memory_snapshot', return_value=snapshot):
            guard = resource_limits.ResourceGuard(4096)
            result = guard.check(additional_bytes=1024 * resource_limits.MIB, force=True)
        self.assertEqual(result, snapshot)

    def test_large_elf_uses_one_worker(self):
        with patch.object(elf_parser.os.path, 'getsize', return_value=133 * resource_limits.MIB), patch.object(
            elf_parser, '_dwarf_worker', return_value=({}, {}, {}, {}),
        ) as worker:
            elf_parser._collect_dwarf_types(str(self.elf_path), 99, 'all', 512)
            worker.assert_called_once_with((str(self.elf_path), 0, 1, 'all', 512))

    def test_worker_cap_and_memory_shares(self):
        with patch.object(elf_parser.os, 'cpu_count', return_value=16), patch.object(
            elf_parser, 'ProcessPoolExecutor',
        ) as pool:
            pool.return_value.__enter__.return_value.map.return_value = iter([
                ({'enum': {'zero': 0}}, {1: {'type': 'UBYTE'}}, {'first': {'type': 'UBYTE'}}, {}),
                ({}, {2: {'type': 'UWORD'}}, {'second': {'type': 'UWORD'}}, {}),
            ])
            result = elf_parser._collect_dwarf_types(str(self.elf_path), 99)
            pool.assert_called_once_with(max_workers=2)
            tasks = pool.return_value.__enter__.return_value.map.call_args.args[1]
            self.assertEqual([task[4] for task in tasks], [682, 682])
            self.assertEqual(set(result[1]), {1, 2})

    def test_low_headroom_reduces_workers(self):
        snapshot = resource_limits.MemorySnapshot(
            self.safe.total, 1600 * resource_limits.MIB + 300 * resource_limits.MIB, self.safe.process,
        )
        with patch.object(resource_limits, 'memory_snapshot', return_value=snapshot), patch.object(
            elf_parser.os, 'cpu_count', return_value=16,
        ), patch.object(elf_parser, '_dwarf_worker', return_value=({}, {}, {}, {})) as worker:
            elf_parser._collect_dwarf_types(str(self.elf_path), 2)
            self.assertEqual(worker.call_args.args[0][2], 1)

    def test_memory_failure_and_broken_workers_are_not_retried(self):
        for failure in (resource_limits.ResourceLimitError('limit'), BrokenProcessPool('terminated')):
            with self.subTest(failure=failure), patch.object(elf_parser.os, 'cpu_count', return_value=16), patch.object(
                elf_parser, 'ProcessPoolExecutor', side_effect=failure,
            ), patch.object(elf_parser, '_dwarf_worker') as retry:
                with self.assertRaises(resource_limits.ResourceLimitError):
                    elf_parser._collect_dwarf_types(str(self.elf_path), 2)
                retry.assert_not_called()

    def make_array(self):
        scalar = SimpleNamespace(
            tag='DW_TAG_base_type',
            attributes={'DW_AT_encoding': SimpleNamespace(value=7), 'DW_AT_byte_size': SimpleNamespace(value=1)},
        )
        dimension = SimpleNamespace(tag='DW_TAG_subrange_type', attributes={'DW_AT_count': SimpleNamespace(value=3)})
        array = SimpleNamespace(
            tag='DW_TAG_array_type', attributes={'DW_AT_type': SimpleNamespace(value=1)},
            get_DIE_from_attribute=lambda name: scalar, iter_children=lambda: iter([dimension]),
        )
        return array

    def test_scalar_array_type_is_resolved_once(self):
        array = self.make_array()
        with patch.object(elf_parser, '_get_enum_reference', wraps=elf_parser._get_enum_reference) as enum:
            leaves = elf_parser._expand_aggregate(array, 'array', 0x1000)
            enum.assert_called_once()
        self.assertEqual([leaf['name'] for leaf in leaves], ['array[0]', 'array[1]', 'array[2]'])
        self.assertEqual([leaf['address'] for leaf in leaves], [0x1000, 0x1001, 0x1002])

    def test_compact_mode_skips_expansion_and_releases_dies(self):
        array = self.make_array()
        variable = SimpleNamespace(
            tag='DW_TAG_variable',
            attributes={
                'DW_AT_name': SimpleNamespace(value=b'array'),
                'DW_AT_type': SimpleNamespace(value=1),
                'DW_AT_location': SimpleNamespace(value=[3, 0, 16, 0, 0]),
            },
            get_DIE_from_attribute=lambda name: array,
        )

        class Unit:
            _dielist = [variable]
            _diemap = [1]

            def __getitem__(self, name):
                return 4

            def iter_DIEs(self):
                return iter([variable])

        unit = Unit()
        dwarf = SimpleNamespace(iter_CUs=lambda: iter([unit]), _cu_cache=[unit], _cu_offsets_map=[0])
        with patch.object(elf_parser, '_expand_aggregate', wraps=elf_parser._expand_aggregate) as expand:
            compact = elf_parser._parse_dwarf_types(dwarf, expansion_mode='none')
            expand.assert_not_called()
            expanded = elf_parser._parse_dwarf_types(dwarf, expansion_mode='arrays')
            expand.assert_called_once()
        self.assertEqual(compact[3], {})
        self.assertEqual(len(expanded[3][0x1000]), 3)
        self.assertEqual(unit._dielist, [])
        self.assertEqual(unit._diemap, [])
        self.assertEqual(dwarf._cu_offsets_map, [0])

    def test_generator_does_not_overwrite_output_when_protection_trips(self):
        output = Path(self.directory.name) / 'output.a2l'
        output.write_text('existing output', encoding='utf-8')
        with patch('generator.a2l_generator.ResourceGuard') as guard:
            guard.return_value.check.side_effect = resource_limits.ResourceLimitError('limit')
            with self.assertRaises(resource_limits.ResourceLimitError):
                generate_a2l({}, {}, output)
        self.assertEqual(output.read_text(encoding='utf-8'), 'existing output')


if __name__ == '__main__':
    unittest.main()
