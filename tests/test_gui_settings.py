import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import gui


class GuiSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.history_path_patch = patch.object(gui, 'HISTORY_PATH', Path(self.directory.name) / 'history.json')
        self.history_path_patch.start()
        self.addCleanup(self.history_path_patch.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = gui.A2LGeneratorGUI(self.root)
        self.addCleanup(self.root.destroy)

    def test_output_name_tracks_new_and_changed_elf_selection(self):
        self.root.deiconify()
        self.root.update()
        with patch.object(gui.filedialog, 'askopenfilename', side_effect=['C:/input/first.elf', 'C:/input/second.elf']):
            self.app.add_elf()
            self.assertEqual(self.app.output_var.get(), 'first.a2l')
            self.app.output_var.set('custom-name.a2l')
            self.app.add_elf()

        self.assertEqual(self.app.output_var.get(), 'second.a2l')
        self.app.elf_listbox.selection_clear(0, tk.END)
        self.app.elf_listbox.selection_set(0)
        self.app._on_elf_selection_changed()
        self.assertEqual(self.app.output_var.get(), 'first.a2l')

    def test_selected_elf_and_map_remain_selected_and_are_used_together(self):
        elf_paths = [Path(self.directory.name) / 'first.elf', Path(self.directory.name) / 'selected.elf']
        map_paths = [Path(self.directory.name) / 'first.map', Path(self.directory.name) / 'selected.map']
        for path in elf_paths + map_paths:
            path.write_text('test input', encoding='utf-8')
        for path in elf_paths:
            self.app.elf_listbox.insert(tk.END, str(path))
        for path in map_paths:
            self.app.map_listbox.insert(tk.END, str(path))
        self.app.elf_listbox.selection_set(1)
        self.app.map_listbox.selection_set(1)

        self.assertEqual(self.app.elf_listbox.curselection(), (1,))
        self.assertEqual(self.app.map_listbox.curselection(), (1,))
        self.assertEqual(self.app._get_single_selection(self.app.elf_listbox), str(elf_paths[1]))
        self.assertEqual(self.app._get_single_selection(self.app.map_listbox), str(map_paths[1]))
        self.app.output_var.set('custom-folder/custom-name.a2l')

        symbols = {'value': {'size': 1, 'address': 1, 'datatype': 'UBYTE'}}
        def write_generated_a2l(elf_data, map_data, output_path, *args, **kwargs):
            Path(output_path).write_text('generated A2L', encoding='utf-8')

        with patch.object(gui, 'parse_elf_fn', return_value=symbols) as parse_elf, \
                patch.object(gui, 'parse_map_fn', return_value={}) as parse_map, \
                patch.object(gui, 'generate_a2l_fn', side_effect=write_generated_a2l), \
            patch.object(self.app, '_run_background', side_effect=lambda operation: operation()), \
                patch.object(gui.messagebox, 'showerror') as show_error, \
                patch.object(self.app.logger, 'log') as log:
            self.app.generate_a2l()

        show_error.assert_not_called()
        self.assertEqual(parse_elf.call_args.args[0], str(elf_paths[1]))
        self.assertEqual(parse_map.call_args.args[0], str(map_paths[1]))
        expected_output = elf_paths[1].parent / 'custom-name.a2l'
        self.assertEqual(self.app.last_output_path, str(expected_output))
        self.assertEqual(self.app.output_var.get(), 'custom-name.a2l')
        self.assertEqual(self.app.open_button.cget('text'), 'Open A2L Folder')
        self.assertTrue(any('Total execution time:' in call.args[0] for call in log.call_args_list))
        with patch.object(gui.sys, 'platform', 'win32'), \
                patch.object(gui.os, 'startfile', create=True) as startfile:
            self.app.open_a2l_folder()
        startfile.assert_called_once_with(str(expected_output.parent))

    def test_card_labels_and_checkboxes_use_white_background(self):
        self.assertEqual(self.app.style.lookup('Card.TLabel', 'background'), '#ffffff')
        self.assertEqual(self.app.style.lookup('Card.TCheckbutton', 'background'), '#ffffff')

    def test_theme_switch_recolors_widgets_and_persists_choice(self):
        self.assertTrue(self.app.theme_switch.winfo_exists())
        self.app.dark_mode_var.set(True)
        self.app.toggle_theme()
        self.assertEqual(self.app.root.cget('bg'), '#20262e')
        self.assertEqual(self.app.style.lookup('Card.TFrame', 'background'), '#2b333d')
        self.assertEqual(self.app.elf_listbox.cget('bg'), '#252d36')
        self.assertEqual(self.app.log_text.cget('bg'), '#252d36')

        self.app.dark_mode_var.set(False)
        self.app.load_history()
        self.assertTrue(self.app.dark_mode_var.get())
        self.assertEqual(self.app.root.cget('bg'), '#20262e')

        self.app.dark_mode_var.set(False)
        self.app.toggle_theme()
        self.assertEqual(self.app.root.cget('bg'), '#f4f5f8')
        self.assertEqual(self.app.elf_listbox.cget('bg'), '#ffffff')

    def test_advanced_selection_uses_dark_palette(self):
        self.app.dark_mode_var.set(True)
        self.app.toggle_theme()

        def inspect_and_close():
            dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
            listboxes = [widget for widget in self._descendants(dialog) if isinstance(widget, tk.Listbox)]
            self.assertEqual(len(listboxes), 2)
            self.assertTrue(all(widget.cget('bg') == '#252d36' for widget in listboxes))
            cancel_button = next(widget for widget in self._descendants(dialog)
                                 if isinstance(widget, gui.ttk.Button) and widget.cget('text') == 'Cancel')
            cancel_button.invoke()

        self.root.after(0, inspect_and_close)
        result = self.app._show_advanced_variable_selection({
            'value': {'size': 1, 'address': 1, 'datatype': 'UBYTE'},
        })
        self.assertIsNone(result)

    def test_generation_settings_fit_without_a_canvas_or_scrollbar(self):
        self.root.geometry('1000x800')
        self.root.deiconify()
        self.root.update()
        body = self.app.generate_button.master.master.winfo_children()[-1]
        self.assertIsInstance(body, gui.ttk.Frame)
        self.assertFalse(any(isinstance(widget, (tk.Canvas, gui.ttk.Scrollbar)) for widget in body.winfo_children()))
        self.assertEqual(set(self.app.if_data_vars), set(gui.IF_DATA_OPTIONS))
        self.assertEqual(self.app._get_selected_if_data_tags(), list(gui.DEFAULT_IF_DATA_TAGS))
        for tag_var in self.app.if_data_vars.values():
            widget = next(widget for widget in self._descendants(body)
                          if isinstance(widget, gui.ttk.Checkbutton)
                          and str(widget.cget('variable')) == str(tag_var))
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
        for widget in (self.app.access_dropdown, self.app.output_entry, self.app.generate_button):
            self.assertTrue(widget.winfo_ismapped())

    @staticmethod
    def _descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from GuiSettingsTests._descendants(child)


if __name__ == '__main__':
    unittest.main()
