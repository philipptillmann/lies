import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from playwright.sync_api import sync_playwright, expect

summary='A human reads news.'
long_text='A human reads the news and learns a new language by reading articles about the world. ' * 5
word_data={'parse':{'wikitext':'==English==\n{{trans-top|human being}}\n* German: {{t+|de|Mensch}}\n{{trans-bottom}}\n{{trans-top|of humans}}\n* German: {{t+|de|menschlich}}, {{t+|de|human}}\n{{trans-bottom}}'}}
def fake_fetch(url):
    if 'wiktionary.org' in url:
        return json.dumps(word_data).encode()
    if 'mymemory' in url:
        return json.dumps({'responseStatus':200,'responseData':{'translatedText':'Mensch'},'matches':[{'segment':'mens','translation':'Person'}]}).encode()
    if url == 'https://example.com/story':
        return ('<article><p>'+long_text+'</p></article>').encode()
    if 'nos.nl' in url:
        return b'<rss><channel><item><title>Een mens leest nieuws</title><description>Een mens leest het nieuws.</description><link>https://example.com/dutch</link></item></channel></rss>'
    if 'bbci.co.uk' in url:
        return ('<rss><channel><item><title>Human news</title><description>'+summary+'</description><link>https://example.com/story</link></item></channel></rss>').encode()
    raise ValueError('Test: Dienst nicht erreichbar.')

with tempfile.TemporaryDirectory() as tmp, patch.object(server,'DB',Path(tmp)/'db.sqlite3'), patch.object(server,'fetch',side_effect=fake_fetch):
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{http.server_port}')
            page.get_by_role('button',name='BBC World abonnieren',exact=True).click()
            page.get_by_role('button',name='Lesen & entdecken').first.click()
            assert page.locator('#reader .body').inner_text()==summary
            page.get_by_role('button',name='Artikeltext hier laden',exact=True).click()
            expect(page.locator('#reader .body')).to_contain_text('new language')
            page.locator('#reader .body').get_by_role('button',name='human übersetzen',exact=True).first.click()
            expect(page.locator('#lookup-result')).to_contain_text('gespeichert')
            assert page.locator('#lookup-result .translations li').count()==3
            assert 'Mensch' in page.locator('#lookup-result').inner_text()
            page.get_by_role('button',name='Schließen',exact=True).click()
            page.locator('#vocab-tab').click()
            assert page.locator('.vocab-card').count()==1
            assert long_text.strip() in page.locator('#vocab-list').inner_text() or 'A human reads the news' in page.locator('#vocab-list').inner_text()
            page.locator('#vocab-language').select_option('nl')
            assert page.locator('.vocab-card').count()==0
            assert page.locator('#export').is_disabled()
            page.locator('#learning').select_option('nl')
            page.locator('#read-tab').click()
            page.get_by_role('button',name='NOS Nieuws abonnieren',exact=True).click()
            page.get_by_role('button',name='Lesen & entdecken').first.click()
            page.get_by_role('button',name='Artikeltext hier laden',exact=True).click()
            expect(page.locator('.reader-note').first).to_contain_text('nicht erreichbar')
            assert page.locator('#reader .body').inner_text()=='Een mens leest het nieuws.'
            page.locator('#reader .body').get_by_role('button',name='mens übersetzen',exact=True).click()
            expect(page.locator('#lookup-result')).to_contain_text('gespeichert')
            assert page.locator('#lookup-result .translations li').count()==2
            page.get_by_role('button',name='Schließen',exact=True).click()
            page.locator('#vocab-tab').click()
            assert page.locator('.vocab-card').count()==1
            assert page.locator('.vocab-card h3').inner_text()=='mens'
            with page.expect_download() as dl:
                page.locator('#export').click()
            exported=json.loads(Path(dl.value.path()).read_text())
            assert len(exported)==1 and exported[0]['source_language']=='nl'
            page.locator('#vocab-language').select_option('en')
            assert page.locator('.vocab-card h3').inner_text()=='human'
            assert page.locator('.vocab-card .translations li').count()==3
            page.reload()
            page.locator('#vocab-tab').click()
            page.locator('#vocab-language').select_option('en')
            assert page.locator('.vocab-card h3').inner_text()=='human'
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            browser.close()
            print('PASS: mobile RSS reading, full article extraction, alternative meanings, persistence, Dutch, separate language lists and filtered JSON export; no browser errors.')
    finally:
        http.shutdown();http.server_close()
