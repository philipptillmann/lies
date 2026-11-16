"""Build and check Docker startup, non-root execution and SQLite persistence.

Requires Docker with Compose v2. Uses a unique Compose project and deletes only
that project's test container/volume. Run from the repository root.
"""
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
# Isolate the test from .env files, the real database, and existing containers.
env = dict(os.environ, LIES_PORT="0", LIES_BIND="127.0.0.1")
project = "lies-test-" + uuid.uuid4().hex[:10]
command = ["docker", "compose", "--project-directory", str(ROOT),
           "--env-file", os.devnull, "-p", project, "-f", str(ROOT / "compose.yaml")]


def compose(*args, capture=False, input=None):
    return subprocess.run(command + list(args), env=env, cwd=ROOT, check=True,
                          text=True, input=input,
                          stdout=subprocess.PIPE if capture else None).stdout


def get(path):
    address = compose("port", "lies", "8000", capture=True).strip()
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open("http://" + address + path, timeout=5) as response:
        return response.read()


try:
    compose("up", "-d", "--build", "--wait", "--wait-timeout", "90")
    assert "nl" in json.loads(get("/api/config"))["languages"]
    assert b"/app.js" in get("/")
    compose("exec", "-T", "lies", "python", "-", input='''
import os
import server
assert os.geteuid() != 0, "Container must run as non-root"
with server.connect() as con:
    con.execute("INSERT INTO feeds(name,language,url) VALUES(?,?,?)", ("Test", "nl", "https://example.com/feed"))
    con.execute("INSERT INTO vocabulary(word,translation,source_language,target_language,sentence,article_title,article_url,translations) VALUES(?,?,?,?,?,?,?,?)", ("mens", "Mensch", "nl", "de", "Een mens leest.", "Test", "https://example.com/story", '[{"text":"Mensch","provider":"Test"}]'))
''')
    compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "90")
    vocabulary = json.loads(get("/api/vocabulary"))
    assert len(vocabulary) == 1 and vocabulary[0]["word"] == "mens"
    assert vocabulary[0]["translations"][0]["text"] == "Mensch"
    assert json.loads(get("/api/feeds"))[0]["language"] == "nl"
    print("PASS: image built; HTTP and healthcheck work; process is non-root; feeds and vocabulary survive container replacement.")
except Exception:
    compose("logs", "--no-color")
    raise
finally:
    compose("down", "--volumes", "--remove-orphans")
