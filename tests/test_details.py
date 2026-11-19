import unittest
from details import parse_details

class DetailTests(unittest.TestCase):
    def test_commented_movie_schema(self):
        result=parse_details('''<script type="application/ld+json">/* <![CDATA[ */ {"@type":"Movie","description":"A &amp; B","image":"https://a.ltrbxd.com/poster.jpg","aggregateRating":{"ratingValue":4.2,"bestRating":5,"ratingCount":120}} /* ]]> */</script>''')
        self.assertEqual(result['rating'],4.2)
        self.assertEqual(result['synopsis'],'A & B')

    def test_graph_missing_optional_fields(self):
        result=parse_details('<script type="application/ld+json">{"@graph":[{"@type":"Movie"}]}</script>')
        self.assertIsNone(result['rating'])
        self.assertEqual(result['synopsis'],'')

    def test_missing_or_malformed_metadata(self):
        for html in ('<html>Blocked</html>','<script type="application/ld+json">broken</script>'):
            with self.assertRaises(ValueError):
                parse_details(html)
