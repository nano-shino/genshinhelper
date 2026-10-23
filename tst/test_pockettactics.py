import unittest

from handlers.genshin_codes import parse_pockettactics_codes

PAGE = """
<html><body><div class="entry-content">
<h2>Active Genshin Impact codes</h2>
<ul>
  <li><strong>ExpertMitya</strong> - 100 Primogems</li>
  <li><strong>PhotoTime</strong> - Hero's Wit</li>
  <li><strong>Primogems</strong> - not a code, but 9 letters</li>
  <li><s><strong>OldCode123</strong></s> - struck through</li>
  <li><strong>ExpiredOne</strong> (expired)</li>
</ul>
<h2>Expired Genshin Impact codes</h2>
<ul>
  <li><strong>GoneCode99</strong></li>
</ul>
<h2>How to redeem</h2>
<ul><li>Open <strong>Settings</strong></li></ul>
</div></body></html>
"""


class PocketTacticsParserTest(unittest.TestCase):
    def test_returns_only_active_codes(self):
        self.assertEqual(parse_pockettactics_codes(PAGE), ["ExpertMitya", "PhotoTime"])

    def test_missing_content_returns_empty(self):
        self.assertEqual(parse_pockettactics_codes("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
