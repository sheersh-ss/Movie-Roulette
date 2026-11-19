import unittest
from cinejoy import exact_matches

class MatchingTests(unittest.TestCase):
    def test_unique_title_year(self):
        links = ['/movie/1368337-the-odyssey-2026', '/movie/1-the-odyssey-1997', '/series/2-the-odyssey-2026', 'https://other.test/movie/3-the-odyssey-2026']
        self.assertEqual(exact_matches('The Odyssey (2026)', links), ['https://cinejoy.pk/movie/1368337-the-odyssey-2026'])

    def test_ambiguous_and_duplicates(self):
        a='/movie/1-the-odyssey-2026'
        self.assertEqual(len(exact_matches('The Odyssey (2026)', [a, a])), 1)
        self.assertEqual(len(exact_matches('The Odyssey (2026)', [a, '/movie/2-the-odyssey-2026'])), 2)

    def test_no_year_no_guess(self):
        self.assertEqual(exact_matches('The Odyssey', ['/movie/1-the-odyssey-2026']), [])

    def test_accents(self):
        self.assertEqual(exact_matches('Amélie (2001)', ['/movie/194-amelie-2001']), ['https://cinejoy.pk/movie/194-amelie-2001'])
