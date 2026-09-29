"""記号変換の衝突回避、無効化、INI の往復を検証する。"""
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'src'))
import config
import ui_settings
from archive_content_cleaner import (normalize_symbols_in_dir,
    scan_archives_for_cleaning, process_single_archive)


class FilenameSettingsTests(unittest.TestCase):
    def test_collision_and_nested_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a!').mkdir()
            (root / 'a!' / 'p!.txt').write_text('original')
            (root / 'a!' / 'p！.txt').write_text('existing')
            self.assertEqual(normalize_symbols_in_dir(folder), 2)
            self.assertEqual((root / 'a！' / 'p！.txt').read_text(), 'existing')
            self.assertEqual((root / 'a！' / 'p！_1.txt').read_text(), 'original')

    def test_scan_toggle_and_archive_rename(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'book!.zip'
            with zipfile.ZipFile(archive, 'w') as out:
                out.writestr('page.txt', 'data')
            options = dict(check_nesting=False, check_long_names=False, fix_extensions=False)
            self.assertEqual(scan_archives_for_cleaning(folder, normalize_symbols=False, **options), [])
            result = scan_archives_for_cleaning(folder, **options)[0]
            old_time = archive.stat().st_mtime_ns
            processed = process_single_archive(result, fix_extensions=False)
            self.assertTrue(processed.success)
            self.assertTrue((Path(folder) / 'book！.zip').exists())
            self.assertEqual(Path(processed.output_path).stat().st_mtime_ns, old_time)

    def test_inside_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'book.zip'
            with zipfile.ZipFile(archive, 'w') as out:
                out.writestr('page!.txt', 'data')
            result = scan_archives_for_cleaning(folder, check_nesting=False, fix_extensions=False)[0]
            self.assertEqual(result.symbol_name_files, ['page!.txt'])
            def extract(path, destination):
                with zipfile.ZipFile(path) as source:
                    source.extractall(destination)
                return True
            def compress(source, destination, *args):
                with zipfile.ZipFile(destination, 'w') as output:
                    for file in Path(source).rglob('*'):
                        if file.is_file():
                            output.write(file, file.relative_to(source))
                return True, ''
            with patch('archive_content_cleaner.extract_archive', extract), patch('archive_content_cleaner.compress_directory', compress):
                processed = process_single_archive(result, fix_extensions=False)
            self.assertTrue(processed.success)
            with zipfile.ZipFile(archive) as output:
                self.assertEqual(output.read('page！.txt'), b'data')

    def test_ini_reset_and_unicode(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'get_exe_dir', return_value=folder):
            self.assertEqual(ui_settings.load_settings(), {})
            ui_settings.save_settings({'clean_symbols_var': False, 'clean_dir_var': 'C:/日本語/100%!'})
            self.assertEqual(ui_settings.load_settings()['clean_symbols_var'], 'False')
            self.assertEqual(ui_settings.load_settings()['clean_dir_var'], 'C:/日本語/100%!')
            os.remove(Path(folder) / config.UI_SETTINGS_FILE)
            self.assertEqual(ui_settings.load_settings(), {})


if __name__ == '__main__':
    unittest.main()
