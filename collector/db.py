import hashlib
import re
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, type TEXT, priority INTEGER DEFAULT 1,
  enabled INTEGER DEFAULT 1, last_fetched_at TEXT, last_status TEXT, last_error TEXT);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT);
CREATE TABLE IF NOT EXISTS articles(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL, url TEXT NOT NULL, url_normalized TEXT NOT NULL UNIQUE, title_key TEXT,
  published_at TEXT, fetched_at TEXT NOT NULL, source_id TEXT NOT NULL, source_name TEXT,
  summary TEXT, summary_kind TEXT DEFAULT 'excerpt', categories TEXT, keywords TEXT,
  importance INTEGER DEFAULT 1, usage_points TEXT, duplicate_of INTEGER,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published_at);
CREATE TABLE IF NOT EXISTS fetch_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT NOT NULL, source_id TEXT, source_name TEXT,
  processed INTEGER DEFAULT 0, success INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, error TEXT);
"""
TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_src|mc_)", re.I)


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:  # 既存DBへの列追加（タイトル日本語訳）
        con.execute("ALTER TABLE articles ADD COLUMN title_ja TEXT")
    except sqlite3.OperationalError:
        pass
    return con


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)]
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(q), ""))


def title_key(title: str) -> str:
    t = re.sub(r"[\W_]+", "", title.lower())
    return hashlib.sha1(t.encode()).hexdigest()[:16] if t else ""
