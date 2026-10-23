"""Extract readable public article text without executing page scripts."""
import json
import re
from html.parser import HTMLParser


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.groups = {}
        self.blocks = []
        self.scripts = []
        self.script = None
        self.next_group = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.script = [] if attrs.get("type", "").lower() == "application/ld+json" else None
        parent = self.stack[-1] if self.stack else {"group": None, "hidden": False}
        marker = attrs.get("class", "") + " " + attrs.get("id", "")
        hidden = parent["hidden"] or tag in {"nav", "aside", "footer", "header", "script", "style", "noscript", "form"} or "hidden" in attrs or attrs.get("aria-hidden") == "true"
        group = parent["group"]
        if not hidden and (tag in {"article", "main"} or attrs.get("role") == "main" or re.search(r"article[-_]body|story[-_]body|article__body", marker, re.I)):
            group = self.next_group
            self.next_group += 1
            self.groups[group] = {"priority": 2 if tag == "article" else 1, "parts": []}
        if not hidden and group is None and attrs.get("data-component") == "text-block":
            group = -1
            self.groups.setdefault(group, {"priority": 1, "parts": []})
        frame = {"tag": tag, "hidden": hidden, "group": group}
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(frame)
        if tag in {"p", "h2", "h3"} and group is not None and not hidden:
            self.blocks.append({"depth": len(self.stack), "group": group, "text": []})
        if tag == "br" and self.blocks:
            self.blocks[-1]["text"].append(" ")

    def handle_data(self, data):
        if self.stack and self.stack[-1]["tag"] == "script" and self.script is not None:
            self.script.append(data)
        if self.blocks and self.stack and not self.stack[-1]["hidden"]:
            self.blocks[-1]["text"].append(data)

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]["tag"] == tag), None)
        if index is None:
            return
        while self.blocks and self.blocks[-1]["depth"] > index:
            block = self.blocks.pop()
            text = re.sub(r"\s+", " ", "".join(block["text"])).strip()
            if text:
                self.groups[block["group"]]["parts"].append(text)
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        del self.stack[index:]


def structured_articles(value):
    if isinstance(value, list):
        for item in value:
            yield from structured_articles(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if any(t in {"NewsArticle", "Article", "ReportageNewsArticle", "AnalysisNewsArticle"} for t in types):
            yield value
        for item in value.values():
            if isinstance(item, (dict, list)):
                yield from structured_articles(item)


def extract_article(raw):
    parser = ArticleParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    candidates = []
    for script in parser.scripts:
        try:
            for article in structured_articles(json.loads(script)):
                if article.get("isAccessibleForFree") in (False, "False", "false"):
                    raise ValueError("Dieser Artikel ist als kostenpflichtig markiert. Bitte das Original öffnen.")
                body = article.get("articleBody")
                if isinstance(body, str) and body.strip():
                    # Structured body is text, never rendered as HTML by the client.
                    candidates.append(re.sub(r"<[^>]+>", " ", body).strip())
        except (json.JSONDecodeError, TypeError):
            continue
    if not candidates:
        groups = [g for g in parser.groups.values() if sum(len(p) for p in g["parts"]) >= 120]
        if groups:
            best = max(groups, key=lambda g: (g["priority"], sum(len(p) for p in g["parts"])))
            candidates.append("\n\n".join(dict.fromkeys(best["parts"])))
    text = max(candidates, key=len, default="")[:100000]
    if len(text) < 120:
        raise ValueError("Kein zusätzlicher Artikeltext gefunden. Nutze den Feed-Auszug oder öffne das Original.")
    return text
