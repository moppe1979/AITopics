"""RSS 2.0 / Atom / RSS 1.0(RDF) を標準ライブラリだけで解析する。"""
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

UA = "AITopicsBot/1.0 (personal RSS reader)"
MAX_BYTES = 5 * 1024 * 1024


def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES)


def _local(tag) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _text(el, *names) -> str:
    for child in el:
        if _local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def strip_html(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", unescape(s)).strip()


def parse_date(s: str):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse(data: bytes) -> list[dict]:
    root = ET.fromstring(data)
    items = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        link = ""
        for c in el:
            if _local(c.tag) != "link":
                continue
            href = c.attrib.get("href")
            if href and c.attrib.get("rel", "alternate") == "alternate":
                link = href
                break
            if (c.text or "").strip() and not link:
                link = c.text.strip()
        items.append({
            "title": strip_html(_text(el, "title")),
            "url": link,
            "published": parse_date(_text(el, "pubdate", "published", "updated", "date")),
            "summary": strip_html(_text(el, "description", "summary", "content", "encoded")),
        })
    return items
