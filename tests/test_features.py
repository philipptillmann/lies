import json
import sqlite3
from unittest.mock import patch
import unittest
import test_server as baseline
import server
from article_text import extract_article


class FeatureTests(unittest.TestCase):
    setUp = baseline.LiesTests.setUp
    tearDown = baseline.LiesTests.tearDown
    payload = baseline.LiesTests.payload
    def test_multiple_meanings_persist(self):
        meanings = [{"text": "Mensch", "sense": "human being", "provider": "Wiktionary"},
                    {"text": "menschlich", "sense": "of humans", "provider": "Wiktionary"}]
        with patch('server.translate', return_value=meanings) as translate:
            result = server.lookup(self.payload())
            self.assertEqual(result['translations'], meanings)
            self.assertEqual(server.lookup(self.payload())['translations'], meanings)
            translate.assert_called_once()
        with server.connect() as con:
            self.assertEqual(server.vocabulary_row(con.execute('SELECT * FROM vocabulary').fetchone())['translations'], meanings)

    def test_migration_preserves_old_words_and_enriches_on_lookup(self):
        with sqlite3.connect(server.DB) as con:
            con.execute('CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, word TEXT, translation TEXT, source_language TEXT, target_language TEXT, sentence TEXT, article_title TEXT, article_url TEXT, created_at TEXT, UNIQUE(word,source_language,target_language))')
            con.execute("INSERT INTO vocabulary VALUES (1,'hello','Hallo','en','de','Hello world.','News','https://example.com','2026-01-01')")
        with server.connect() as con:
            row = server.vocabulary_row(con.execute('SELECT * FROM vocabulary').fetchone())
            self.assertEqual(row['translation'], 'Hallo')
            self.assertEqual(row['created_at'], '2026-01-01')
        with patch('server.translate', return_value=[{'text':'Hallo','provider':'MyMemory'}]):
            server.lookup(self.payload())
        with server.connect() as con:
            self.assertIsNotNone(con.execute('SELECT translations FROM vocabulary').fetchone()[0])

    def test_legacy_service_failure_keeps_word_and_allows_retry(self):
        with server.connect() as con:
            con.execute("INSERT INTO vocabulary(word,translation,source_language,target_language,sentence,article_title,article_url) VALUES('hello','Hallo','en','de','Old','','')")
        with patch('server.translate', side_effect=ValueError('offline')):
            self.assertEqual(server.lookup(self.payload())['translation'], 'Hallo')
        with server.connect() as con:
            self.assertIsNone(con.execute('SELECT translations FROM vocabulary').fetchone()[0])

    def test_wiktionary_keeps_distinct_senses(self):
        text = '''==English==
===Adjective===
{{trans-top|of humans}}
* German: {{t+|de|menschlich}}, {{t|de|human}}
{{trans-bottom}}
===Noun===
{{trans-top|human being}}
* German: {{t+|de|Mensch|m}}, {{t+|de|Mensch|m}}
{{trans-bottom}}
==Dutch==
* German: {{t|de|wrong}}
'''
        with patch('server.fetch', return_value=json.dumps({'parse':{'wikitext':text}}).encode()):
            result = server.translate('human','en','de')
        self.assertEqual([x['text'] for x in result], ['menschlich','human','Mensch'])
        self.assertEqual(result[2]['sense'], 'human being')

    def test_memory_excludes_fuzzy_sentence_matches(self):
        data = {'responseStatus':200,'responseData':{'translatedText':'Mensch'},'matches':[
            {'segment':'human','translation':'menschlich'},
            {'segment':'human rights','translation':'Menschenrechte'},
            {'segment':'HUMAN','translation':'Mensch'}]}
        with patch('server.wiktionary_translations',return_value=[]), patch('server.fetch',return_value=json.dumps(data).encode()):
            self.assertEqual([x['text'] for x in server.translate('human','en','de')], ['Mensch','menschlich'])

    def test_dutch_lookup_and_feed(self):
        self.assertIn('nl', server.LANGS)
        self.assertTrue(any(f['language']=='nl' for f in server.CATALOG))
        data=self.payload();data.update(word='mens',source='nl')
        with patch('server.translate',return_value=[{'text':'Mensch','provider':'MyMemory'}]):
            self.assertTrue(server.lookup(data)['saved'])

    def test_article_excludes_navigation_and_scripts(self):
        paragraph='A long paragraph about language learning and current events. ' * 4
        raw=('<main><nav><p>Navigation</p></nav><article><p>'+paragraph+'<strong>Important</strong>.</p><script>malicious()</script></article><aside><p>Related story</p></aside></main>').encode()
        text=extract_article(raw)
        self.assertIn('Important', text)
        self.assertNotIn('malicious', text)
        self.assertNotIn('Navigation', text)
        self.assertNotIn('Related', text)

    def test_bbc_text_blocks_without_article_tag(self):
        paragraph='A paragraph from the BBC text block. ' * 5
        self.assertIn(paragraph.strip(),extract_article(('<div data-component="text-block"><div><p>'+paragraph+'</p></div></div>').encode()))

    def test_jsonld_and_paywall(self):
        body='News article body with enough text for the reading view. ' * 4
        data={'@graph':[{'@type':'NewsArticle','articleBody':body}]}
        html=('<script type="application/ld+json">'+json.dumps(data)+'</script>').encode()
        self.assertEqual(extract_article(html),body.strip())
        data['@graph'][0]['isAccessibleForFree']=False
        with self.assertRaisesRegex(ValueError,'kostenpflichtig'):
            extract_article(('<script type="application/ld+json">'+json.dumps(data)+'</script>').encode())

    def test_no_readable_body_fails(self):
        with self.assertRaises(ValueError):
            extract_article(b'<html><nav><p>Menu</p></nav><p>Teaser</p></html>')

    def test_full_article_requires_subscribed_story_and_caches(self):
        body='A full article paragraph about humans learning languages. ' * 5
        story={'url':'https://example.com/story','text':'Short summary'}
        with patch('server.feed_articles',return_value=[story]),patch('server.fetch',return_value=('<article><p>'+body+'</p></article>').encode()) as fetch:
            server.ARTICLE_CACHE.clear()
            self.assertEqual(server.full_article({'feed_id':1,'url':story['url']})['text'],body.strip())
            server.full_article({'feed_id':1,'url':story['url']})
            fetch.assert_called_once()
            with self.assertRaises(ValueError):
                server.full_article({'feed_id':1,'url':'https://example.com/other'})
