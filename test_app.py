import unittest

from app import parse_rss_items


class ParseRssItemsTest(unittest.TestCase):
    def test_parse_rss_items(self):
        xml = b"""
        <rss><channel>
            <item>
                <title>Hello</title>
                <link>https://example.com/1</link>
                <description>Summary</description>
                <pubDate>Tue, 10 Oct 2023 10:00:00 GMT</pubDate>
            </item>
        </channel></rss>
        """

        items = parse_rss_items(xml, "unit-test")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello")
        self.assertEqual(items[0]["url"], "https://example.com/1")
        self.assertIn("2023-10-10", items[0]["published_at"])


if __name__ == "__main__":
    unittest.main()
