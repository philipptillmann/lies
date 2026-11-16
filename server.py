#!/usr/bin/env python3
"""Lies: single-user local RSS reader. Python standard library only."""
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from article_text import extract_article
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "lies.sqlite3"
LANGS = {"de": "Deutsch", "en": "Englisch", "fr": "Französisch", "es": "Spanisch", "it": "Italienisch", "pt": "Portugiesisch", "nl": "Niederländisch"}
CATALOG = [
    {"name": "NOS Nieuws", "language": "nl", "url": "https://feeds.nos.nl/nosnieuwsalgemeen"},
    {"name": "BBC World", "language": "en", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "language": "en", "url": "https://www.theguardian.com/world/rss"},
    {"name": "tagesschau", "language": "de", "url": "https://www.tagesschau.de/xml/rss2/"},
    {"name": "France 24", "language": "fr", "url": "https://www.france24.com/fr/rss"},
    {"name": "El País", "language": "es", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
    {"name": "ANSA", "language": "it", "url": "https://www.ansa.it/sito/ansait_rss.xml"},
]
CACHE = {}
ARTICLE_CACHE = {}
SCHEMA_LOCK = threading.RLock()

def connect():
    with SCHEMA_LOCK:
        return _connect()

def _connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS feeds (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, language TEXT NOT NULL, url TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS vocabulary (
      id INTEGER PRIMARY KEY, word TEXT NOT NULL, translation TEXT NOT NULL,
      source_language TEXT NOT NULL, target_language TEXT NOT NULL,
      sentence TEXT NOT NULL, article_title TEXT NOT NULL, article_url TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(word, source_language, target_language));
    """)
    columns = {r["name"] for r in con.execute("PRAGMA table_info(vocabulary)")}
    if "translations" not in columns:
        con.execute("ALTER TABLE vocabulary ADD COLUMN translations TEXT")
        con.commit()
    return con

def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Bitte eine öffentliche HTTPS-Adresse ohne Zugangsdaten verwenden.")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Lokale und private Adressen sind nicht erlaubt.")
    return url

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url):
    safe_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Lies/0.1 RSS language reader", "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, text/html"})
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=12) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Die Antwort ist zu groß.")
    return raw

def plain(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()

def link_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        return url if p.scheme in ("http", "https") and p.hostname and not p.username and not p.password else ""
    except ValueError:
        return ""

def parse_feed(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Dieser XML-Feed enthält nicht unterstützte Deklarationen.")
    root = ET.fromstring(raw)
    # Normalize namespace names to support RSS, Atom and content:encoded.
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    nodes = root.findall("./channel/item") or root.findall("./entry") or root.findall("./item")
    articles = []
    for node in nodes[:60]:
        def value(*names):
            for name in names:
                found = node.find(name)
                if found is not None:
                    text = "".join(found.itertext())
                    if text.strip():
                        return text
            return ""
        link = value("link")
        for element in node.findall("link"):
            if element.get("rel", "alternate") == "alternate" and element.get("href"):
                link = element.get("href")
                break
        title = plain(value("title"))
        text = plain(value("encoded", "content", "description", "summary"))
        if title:
            articles.append({"title": title, "text": text, "url": link_url(link),
                             "date": plain(value("pubDate", "published", "updated"))})
    if not articles:
        raise ValueError("Keine lesbaren Beiträge im RSS-/Atom-Feed gefunden.")
    return articles

def unique_translations(items):
    result, seen = [], set()
    for item in items:
        text = plain(item.get("text", ""))[:200]
        sense = plain(item.get("sense", "")).replace("''", "")[:300]
        key = (text.casefold(), sense.casefold())
        if text and key not in seen:
            entry = {"text": text, "sense": sense, "provider": item.get("provider", "MyMemory")}
            if item.get("source_url"):
                entry.update(source_url=item["source_url"], license="CC BY-SA 4.0")
            result.append(entry)
            seen.add(key)
    return result[:20]


def wiktionary_translations(word, source, target):
    # English entries contain multilingual translation tables and sense labels.
    # Non-English source languages fall back to MyMemory below.
    if source != "en":
        return []
    query = urllib.parse.urlencode({"action": "parse", "page": word, "prop": "wikitext", "format": "json", "formatversion": "2"})
    data = json.loads(fetch("https://en.wiktionary.org/w/api.php?" + query))
    text = data.get("parse", {}).get("wikitext", "")
    if not isinstance(text, str):
        return []
    english = re.search(r"^==English==\s*$(.*?)(?=^==[^=]+==\s*$|\Z)", text, re.M | re.S)
    if not english:
        return []
    sense, result = "", []
    for line in english.group(1).splitlines():
        heading = re.search(r"\{\{trans-top\|([^}|]*)", line)
        if heading:
            sense = re.sub(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]", lambda m: m.group(2) or m.group(1), heading.group(1))
        if "{{trans-bottom" in line:
            sense = ""
        if not line.lstrip().startswith("*"):
            continue
        pattern = r"\{\{(?:t|t\+|t-check|t\+check|tt|tt\+)\|" + re.escape(target) + r"\|([^}|]+)"
        for match in re.finditer(pattern, line):
            result.append({"text": match.group(1), "sense": sense, "provider": "Wiktionary", "source_url": "https://en.wiktionary.org/wiki/" + urllib.parse.quote(word, safe="")})
    return unique_translations(result)


def translate(word, source, target):
    if source == target:
        raise ValueError("Bitte unterschiedliche Lern- und Übersetzungssprachen auswählen.")
    try:
        dictionary = wiktionary_translations(word, source, target)
    except (ValueError, OSError, urllib.error.URLError):
        dictionary = []
    if dictionary:
        return dictionary
    query = urllib.parse.urlencode({"q": word, "langpair": source + "|" + target})
    data = json.loads(fetch("https://api.mymemory.translated.net/get?" + query))
    if str(data.get("responseStatus")) != "200" or data.get("quotaFinished"):
        raise ValueError("Übersetzungsdienst nicht verfügbar oder Tageskontingent erreicht. Bitte später erneut versuchen.")
    items = [{"text": data.get("responseData", {}).get("translatedText", ""), "provider": "MyMemory"}]
    for match in data.get("matches", []):
        # Fuzzy sentence matches are not alternative meanings of this word.
        if plain(match.get("segment", "")).casefold() == word.casefold():
            items.append({"text": match.get("translation", ""), "provider": "MyMemory"})
    result = unique_translations(items)
    if not result:
        raise ValueError("Keine Übersetzung gefunden.")
    return result


def vocabulary_row(row):
    item = dict(row)
    item["translations"] = json.loads(item["translations"]) if item.get("translations") else [{"text": item["translation"], "sense": "", "provider": "Gespeichert"}]
    return item


def feed_articles(feed_id):
    with connect() as con:
        feed = con.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
    if not feed:
        raise ValueError("Abo nicht gefunden.")
    cached = CACHE.get(feed["url"])
    if not cached or time.monotonic() - cached[0] > 300:
        cached = (time.monotonic(), parse_feed(fetch(feed["url"])))
        CACHE[feed["url"]] = cached
    return cached[1]


def full_article(data):
    url = str(data.get("url", ""))
    articles = feed_articles(int(data.get("feed_id", 0)))
    original = next((a for a in articles if a["url"] == url and url), None)
    if not original:
        raise ValueError("Dieser Artikel gehört nicht zur ausgewählten Quelle. Bitte den Feed neu laden.")
    cached = ARTICLE_CACHE.get(url)
    if cached and time.monotonic() - cached[0] < 1800:
        return {"text": cached[1]}
    # Upgrade legacy HTTP feed links; never download insecure article pages.
    parts = urllib.parse.urlsplit(url)
    secure = urllib.parse.urlunsplit(parts._replace(scheme="https"))
    text = extract_article(fetch(secure))
    if len(text) <= len(original["text"]) + 40:
        raise ValueError("Kein längerer Artikeltext gefunden. Der Feed-Auszug bleibt sichtbar.")
    if len(ARTICLE_CACHE) >= 100:
        ARTICLE_CACHE.pop(next(iter(ARTICLE_CACHE)), None)
    ARTICLE_CACHE[url] = (time.monotonic(), text)
    return {"text": text}


def lookup(data):
    word = str(data.get("word", "")).strip().lower()
    source, target = data.get("source"), data.get("target")
    if source not in LANGS or target not in LANGS or source == target:
        raise ValueError("Bitte zwei unterschiedliche unterstützte Sprachen wählen.")
    if not word or len(word) > 80 or not any(c.isalpha() for c in word) or any(not (c.isalpha() or c in "'’-") for c in word):
        raise ValueError("Bitte ein einzelnes Wort auswählen.")
    sentence = str(data.get("sentence", ""))[:5000]
    title = str(data.get("article_title", ""))[:500]
    url = link_url(str(data.get("article_url", ""))[:2000])
    with connect() as con:
        old = con.execute("SELECT translation, translations FROM vocabulary WHERE word=? AND source_language=? AND target_language=?", (word, source, target)).fetchone()
    if old and old["translations"]:
        translations = json.loads(old["translations"])
    else:
        try:
            translations = translate(word, source, target)
        except (ValueError, OSError, urllib.error.URLError):
            if not old:
                raise
            translations = [{"text": old["translation"], "sense": "", "provider": "Gespeichert"}]
            # Leave legacy cache unfilled so a later lookup can retry enrichment.
    translation = translations[0]["text"]
    encoded = None if translations[0].get("provider") == "Gespeichert" else json.dumps(translations, ensure_ascii=False)
    with connect() as con:
        con.execute("""INSERT INTO vocabulary(word,translation,source_language,target_language,sentence,article_title,article_url,translations)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(word,source_language,target_language)
        DO UPDATE SET translation=excluded.translation, translations=excluded.translations, sentence=excluded.sentence, article_title=excluded.article_title, article_url=excluded.article_url""",
        (word, translation, source, target, sentence, title, url, encoded))
    return {"word": word, "translation": translation, "translations": translations, "saved": True}

class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/api/config":
                return self.respond(200, {"languages": LANGS, "catalog": CATALOG})
            if path in ("/api/feeds", "/api/vocabulary"):
                table = "feeds" if path.endswith("feeds") else "vocabulary"
                with connect() as con:
                    rows = [(vocabulary_row(r) if table == "vocabulary" else dict(r)) for r in con.execute("SELECT * FROM " + table + " ORDER BY id DESC")]
                return self.respond(200, rows)
            if path.startswith("/api/articles/"):
                return self.respond(200, feed_articles(int(path.rsplit("/", 1)[1])))
            files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if path not in files:
                return self.respond(404, {"error": "Nicht gefunden."})
            filename, mime = files[path]
            body = (ROOT / "static" / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self.respond(400, {"error": friendly(exc)})

    def do_POST(self):
        # Reject cross-site mutations; this prototype has no public multi-user API.
        origin = self.headers.get("Origin")
        if self.headers.get("Sec-Fetch-Site") == "cross-site" or (origin and origin != "http://" + self.headers.get("Host", "")):
            return self.respond(403, {"error": "Fremder Ursprung nicht erlaubt."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 12000 or self.headers.get_content_type() != "application/json":
                raise ValueError("Ungültige Anfrage.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Ungültige Anfrage.")
            if self.path == "/api/article":
                return self.respond(200, full_article(data))
            if self.path == "/api/lookup":
                return self.respond(200, lookup(data))
            if self.path == "/api/feeds":
                name, language, url = str(data.get("name", "")).strip(), data.get("language"), str(data.get("url", "")).strip()
                if not name or len(name) > 100 or language not in LANGS or len(url) > 2000:
                    raise ValueError("Name, Sprache und gültige Feed-Adresse angeben.")
                articles = parse_feed(fetch(url))
                with connect() as con:
                    con.execute("INSERT INTO feeds(name,language,url) VALUES(?,?,?)", (name, language, url))
                CACHE[url] = (time.monotonic(), articles)
                return self.respond(201, {"ok": True})
            if self.path in ("/api/feeds/delete", "/api/vocabulary/delete"):
                table = "feeds" if self.path.startswith("/api/feeds") else "vocabulary"
                with connect() as con:
                    con.execute("DELETE FROM " + table + " WHERE id=?", (int(data["id"]),))
                return self.respond(200, {"ok": True})
            self.respond(404, {"error": "Nicht gefunden."})
        except sqlite3.IntegrityError:
            self.respond(409, {"error": "Dieser Feed ist bereits abonniert."})
        except Exception as exc:
            self.respond(400, {"error": friendly(exc)})

def friendly(exc):
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ET.ParseError):
        return "Der Dienst hat keinen gültigen RSS-/Atom-Feed geliefert."
    return "Der Dienst ist gerade nicht erreichbar oder liefert eine ungültige Antwort. Bitte erneut versuchen."

if __name__ == "__main__":
    with connect():
        pass
    port = int(os.environ.get("PORT", "8000"))
    print(f"Lies läuft auf http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

