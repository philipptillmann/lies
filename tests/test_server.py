import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import server

class LiesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(server, "DB", Path(self.tmp.name) / "test.sqlite3")
        self.db.start()
    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()
    def test_rss_html_and_script_link(self):
        rows = server.parse_feed(b'<rss><channel><item><title>A &amp; B</title><description>&lt;p&gt;Hello world.&lt;/p&gt;</description><link>javascript:alert(1)</link></item></channel></rss>')
        self.assertEqual(rows[0]["title"], "A & B")
        self.assertEqual(rows[0]["text"], "Hello world.")
        self.assertEqual(rows[0]["url"], "")
    def test_atom_namespaces(self):
        rows = server.parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Bonjour</title><link href="https://example.com/story"/><content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Bonjour le monde.</p></div></content></entry></feed>')
        self.assertEqual(rows[0]["text"], "Bonjour le monde.")
        self.assertEqual(rows[0]["url"], "https://example.com/story")
    def test_entities_rejected(self):
        with self.assertRaises(ValueError):
            server.parse_feed(b'<!DOCTYPE rss [<!ENTITY x "hello">]><rss/>')
    def test_private_addresses_rejected(self):
        with patch("server.socket.getaddrinfo", return_value=[(2,1,6,"",("127.0.0.1",443))]):
            with self.assertRaises(ValueError):
                server.safe_url("https://example.com/rss")
        for url in ("http://example.com", "https://user:pass@example.com", "https://example.com:8080"):
            with self.assertRaises(ValueError):
                server.safe_url(url)
    def payload(self, **changes):
        return dict(word="Hello", source="en", target="de", sentence="Hello world.", article_title="News", article_url="https://example.com", **changes)
    def test_lookup_persists_context_and_reuses_translation(self):
        with patch("server.translate", return_value="Hallo") as translate:
            self.assertTrue(server.lookup(self.payload())["saved"])
            data=self.payload()
            data["sentence"]="Hello again."
            server.lookup(data)
            translate.assert_called_once_with("hello", "en", "de")
        with server.connect() as con:
            rows=con.execute("SELECT * FROM vocabulary").fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["sentence"],"Hello again.")
        self.assertEqual(rows[0]["translation"],"Hallo")
    def test_failure_does_not_save(self):
        with patch("server.translate", side_effect=ValueError("quota")):
            with self.assertRaises(ValueError):
                server.lookup(self.payload())
        with server.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0],0)
    def test_quota_response_rejected(self):
        with patch("server.fetch", return_value=json.dumps({"responseStatus":403,"responseData":{"translatedText":"QUOTA EXCEEDED"}}).encode()):
            with self.assertRaises(ValueError):
                server.translate("hello","en","de")
    def test_same_language_rejected(self):
        data=self.payload()
        data["target"]="en"
        with self.assertRaises(ValueError):
            server.lookup(data)

if __name__ == "__main__":
    unittest.main()
