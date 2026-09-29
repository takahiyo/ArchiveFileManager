"""丸数字フォルダを含む話数整理と、失敗時の継続を検証する。"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from archive_content_cleaner import scan_archives_for_cleaning, batch_clean_archives
from folder_normalizer import natural_sort_key, organize_chapters_and_flatten


class ChapterRegressionTests(unittest.TestCase):
    def test_original_backups_excluded_by_default_and_can_be_included(self):
        """大小文字・連番・重複した退避名を除外し、解除時は再抽出する。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'parent_Original'
            root.mkdir()
            names = ['book.zip', 'book_Original.zip', 'book_original_1.zip',
                     'book_Original_Original.zip', 'other_ORIGINAL.zip']
            for name in names:
                with zipfile.ZipFile(root / name, 'w') as archive:
                    archive.writestr('第１話/1.jpg', b'one')
                    archive.writestr('第２話/1.jpg', b'two')
            options = dict(check_chapter_organize=True, fix_extensions=False)
            scans = scan_archives_for_cleaning(folder, **options)
            self.assertEqual([Path(s.archive_path).name for s in scans], ['book.zip'])
            scans = scan_archives_for_cleaning(folder, exclude_original=False, **options)
            self.assertEqual({Path(s.archive_path).name for s in scans}, set(names))

    def test_unicode_natural_sort(self):
        names = ['❺', '①', '²', '第１０話', '第２話', '10.jpg', '2.jpg']
        ordered = sorted(names, key=natural_sort_key)
        self.assertLess(ordered.index('2.jpg'), ordered.index('10.jpg'))
        self.assertLess(ordered.index('第２話'), ordered.index('第１０話'))
        for name in ['❺', '①', '²']:
            self.assertIn(name, ordered)

    def test_flatten_preserves_all_file_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entries = {'❺/0_1.jpg': b'volume', 'Cover/1.jpg': b'cover',
                       '第２話/2.jpg': b'p2', '第２話/10.jpg': b'p10',
                       '第１０話/1.jpg': b'chapter10'}
            for name, data in entries.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            self.assertEqual(organize_chapters_and_flatten(folder), (1, 3, 5))
            self.assertEqual(sorted(p.read_bytes() for p in root.iterdir()), sorted(entries.values()))
            self.assertEqual((root / 'Cover_001.jpg').read_bytes(), b'cover')
            self.assertEqual((root / 'v002_001.jpg').read_bytes(), b'p2')
            self.assertEqual((root / 'v002_002.jpg').read_bytes(), b'p10')

    def test_failure_preserves_original_and_continues_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ['a.zip', 'b.zip']:
                with zipfile.ZipFile(Path(folder) / name, 'w') as archive:
                    archive.writestr('❺/1.jpg', b'one')
                    archive.writestr('第２話/1.jpg', b'two')
            before = {p.name: p.read_bytes() for p in Path(folder).iterdir()}
            scans = scan_archives_for_cleaning(folder, check_chapter_organize=True)
            self.assertEqual(len(scans), 2)
            progress = []
            with patch('folder_normalizer.organize_chapters_and_flatten', side_effect=ValueError('test failure')):
                with self.assertLogs('archive_content_cleaner', level='ERROR'):
                    results = batch_clean_archives(scans, do_chapter_organize=True,
                        progress_callback=lambda current, total: progress.append((current, total)))
            self.assertEqual(progress, [(1, 2), (2, 2)])
            self.assertTrue(all(not r.success and 'ValueError' in r.error_detail for r in results))
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(folder).iterdir()})


if __name__ == '__main__':
    unittest.main()
