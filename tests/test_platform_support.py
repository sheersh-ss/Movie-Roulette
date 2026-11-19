import unittest
from pathlib import Path
from platform_support import cache_path, font_family

class PlatformTests(unittest.TestCase):
    def test_mac(self):
        self.assertEqual(cache_path('darwin','/home/test',{}),Path('/home/test/Library/Application Support/Movie Roulette/top500.json'))
        self.assertEqual(font_family('darwin'),'Helvetica Neue')

    def test_windows(self):
        self.assertEqual(cache_path('win32','/home/test',{'LOCALAPPDATA':'/local'}),Path('/local/Movie Roulette/top500.json'))
        self.assertEqual(cache_path('win32','/home/test',{}),Path('/home/test/AppData/Local/Movie Roulette/top500.json'))
        self.assertEqual(font_family('win32'),'Segoe UI')

    def test_linux(self):
        self.assertEqual(cache_path('linux','/home/test',{'XDG_CACHE_HOME':'/cache'}),Path('/cache/Movie Roulette/top500.json'))
        self.assertEqual(cache_path('linux','/home/test',{'XDG_CACHE_HOME':'relative'}),Path('/home/test/.cache/Movie Roulette/top500.json'))
        self.assertEqual(font_family('linux'),'DejaVu Sans')
