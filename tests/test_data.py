import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
import data


class DataTests(unittest.TestCase):
    def test_both_markup_generations(self):
        html = '''<li class="numbered-list-item"><div data-item-link="/film/a/" data-item-name="A &amp; B (2000)"></div><p class="list-number">1</p></li>
        <li class="numbered-list-item"><div data-film-slug="b"><img alt="B"></div><p class="list-number">2</p></li>'''
        films = data.parse_page(html)
        self.assertEqual(films[0]['title'], 'A & B (2000)')
        self.assertEqual(films[1]['url'], 'https://letterboxd.com/film/b/')

    def test_snapshot_and_corrupt_cache_fallback(self):
        obj = data.load(data.BUNDLED)
        self.assertEqual(len(obj['films']), 500)
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache.json'
            data.save(obj, cache)
            self.assertEqual(data.load(cache), obj)
            cache.write_text('{broken')
            with patch.object(data, 'CACHE', cache):
                fallback, label = data.fallback()
                self.assertEqual(label, 'Bundled snapshot')
                self.assertEqual(fallback, obj)

    def test_invalid_snapshot_rejected(self):
        films = data.load(data.BUNDLED)['films']
        with self.assertRaises(ValueError):
            data.validate(films[:100])
        films[1] = films[0]
        with self.assertRaises(ValueError):
            data.validate(films)

    def test_bounded_retries(self):
        with patch('requests.Session.get', side_effect=requests.Timeout('offline')) as get, patch('data.time.sleep'):
            with self.assertRaises(RuntimeError):
                data.fetch()
            self.assertEqual(get.call_count, 3)

    def test_every_animation_lands_on_selected_rank(self):
        for index in range(500):
            target = (-(index + .5) * .72) % 360
            for start in (0, 123.45, 359.9):
                travel = 360 * 7 + (target - start) % 360
                angle = (start + travel) % 360
                rank = int(((-angle) % 360) / .72) % 500 + 1
                self.assertEqual(rank, index + 1)


if __name__ == '__main__':
    unittest.main()
