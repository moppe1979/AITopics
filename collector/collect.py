"""収集 → SQLite保存 → 静的JSON出力。

使い方:  python collector/collect.py [--no-fetch] [--only SOURCE_ID]
  --no-fetch  取得せず、DBから JSON だけ再出力する
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import classify as clf  # noqa: E402
import db as dbm  # noqa: E402
import feed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
CATEGORIES = {
    "AI": "生成AI・LLM・AIサービス全般",
    "AIエージェント": "AIエージェント・AI開発支援ツール",
    "SI・システム開発": "システム開発・API・Webアプリ・OSS",
    "クラウド・インフラ": "クラウド・サーバー・ネットワーク",
    "データベース・データ連携": "DB・SQL・データ連携",
    "ローコード・業務自動化": "Power Platform・ローコード・RPA",
    "セキュリティ": "サイバーセキュリティ・脆弱性",
    "製造業・IoT": "スマートファクトリー・IoT・現場DX",
    "その他": "上記に該当しないもの",
}
SUMMARY_MAX = 220
EXPORT_DAYS = 120
EXPORT_MAX = 3000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_env_file() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def sync_sources(con) -> list[dict]:
    cfg = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
    for s in cfg:
        con.execute(
            """INSERT INTO sources(id,name,url,type,priority,enabled) VALUES(?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url,type=excluded.type,
               priority=excluded.priority,enabled=excluded.enabled""",
            (s["id"], s["name"], s["url"], s.get("type", "rss"), s.get("priority", 1), int(s.get("enabled", True))))
    for name, desc in CATEGORIES.items():
        con.execute("INSERT OR IGNORE INTO categories(name,description) VALUES(?,?)", (name, desc))
    con.commit()
    return cfg


def store_item(con, src, it, run_at) -> bool:
    """新規保存なら True、重複（既存）なら False。"""
    if not it["title"] or not it["url"].startswith(("http://", "https://")):
        raise ValueError("タイトルまたはURLが不正")
    if it["published"] and it["published"] < datetime.now(timezone.utc) - timedelta(days=EXPORT_DAYS):
        return False  # 保持期間より古い記事は保存しない
    norm = dbm.normalize_url(it["url"])
    if con.execute("SELECT 1 FROM articles WHERE url_normalized=?", (norm,)).fetchone():
        return False
    summary = it["summary"][:SUMMARY_MAX] + ("…" if len(it["summary"]) > SUMMARY_MAX else "")
    cats, kws = clf.classify(it["title"], it["summary"], src["name"])
    imp = clf.importance(it["title"], it["summary"], cats, src["priority"])
    up = clf.usage_points(cats)
    tkey = dbm.title_key(it["title"])
    dup = con.execute("SELECT id FROM articles WHERE title_key=? AND duplicate_of IS NULL", (tkey,)).fetchone() if tkey else None
    pub = it["published"].isoformat(timespec="seconds") if it["published"] else None
    con.execute(
        """INSERT INTO articles(title,url,url_normalized,title_key,published_at,fetched_at,source_id,source_name,
           summary,summary_kind,categories,keywords,importance,usage_points,duplicate_of,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (it["title"], it["url"], norm, tkey, pub, run_at, src["id"], src["name"],
         summary or None, "excerpt" if summary else "none", json.dumps(cats, ensure_ascii=False),
         json.dumps(kws, ensure_ascii=False), imp, up, dup["id"] if dup else None, run_at, run_at))
    return True


def reclassify(con) -> None:
    """rules.json の変更を既存記事にも反映する。"""
    prio = {r["id"]: r["priority"] for r in con.execute("SELECT id,priority FROM sources")}
    for r in con.execute("SELECT id,title,summary,source_name,source_id FROM articles").fetchall():
        cats, kws = clf.classify(r["title"], r["summary"] or "", r["source_name"] or "")
        imp = clf.importance(r["title"], r["summary"] or "", cats, prio.get(r["source_id"], 1))
        con.execute("UPDATE articles SET categories=?,keywords=?,importance=?,usage_points=? WHERE id=?",
                    (json.dumps(cats, ensure_ascii=False), json.dumps(kws, ensure_ascii=False), imp, clf.usage_points(cats), r["id"]))
    con.commit()


def run_fetch(con, only=None) -> None:
    run_at = now_iso()
    rows = con.execute("SELECT * FROM sources WHERE enabled=1").fetchall()
    for src in rows:
        if only and src["id"] != only:
            continue
        ok = fail = processed = 0
        error = None
        try:
            items = feed.parse(feed.fetch(src["url"]))
            processed = len(items)
            if not items:
                raise ValueError("記事が0件（フィード形式の変更または空）")
            for it in items:
                try:
                    if store_item(con, src, it, run_at):
                        ok += 1
                except Exception as e:  # 1記事の失敗で全体を止めない
                    fail += 1
                    error = f"記事保存失敗: {e}"
            status = "ok" if not fail else "partial"
        except Exception as e:
            status, error = "error", f"{type(e).__name__}: {e}"
            fail = max(fail, 1)
        con.execute("UPDATE sources SET last_fetched_at=?,last_status=?,last_error=? WHERE id=?",
                    (run_at, status, error, src["id"]))
        con.execute("INSERT INTO fetch_logs(run_at,source_id,source_name,processed,success,failed,error) VALUES(?,?,?,?,?,?,?)",
                    (run_at, src["id"], src["name"], processed, ok, fail, error))
        con.commit()
        print(f"[{status:7}] {src['name']}: 取得{processed} 新規{ok} 失敗{fail}" + (f"  ({error})" if error else ""))


def export_json(con, out: Path) -> None:
    since = (datetime.now(timezone.utc) - timedelta(days=EXPORT_DAYS)).isoformat(timespec="seconds")
    arts = []
    for r in con.execute(
            """SELECT * FROM articles WHERE COALESCE(published_at,fetched_at)>=? AND duplicate_of IS NULL
               ORDER BY COALESCE(published_at,fetched_at) DESC LIMIT ?""", (since, EXPORT_MAX)):
        arts.append({
            "id": r["id"], "title": r["title"], "url": r["url"], "publishedAt": r["published_at"],
            "fetchedAt": r["fetched_at"], "sourceId": r["source_id"], "source": r["source_name"],
            "summary": r["summary"], "summaryKind": r["summary_kind"],
            "categories": json.loads(r["categories"] or "[]"), "keywords": json.loads(r["keywords"] or "[]"),
            "importance": r["importance"], "usagePoints": r["usage_points"]})
    sources = [dict(id=r["id"], name=r["name"], url=r["url"], enabled=bool(r["enabled"]),
                    lastFetchedAt=r["last_fetched_at"], status=r["last_status"], error=r["last_error"])
               for r in con.execute("SELECT * FROM sources ORDER BY priority DESC, name")]
    logs = [dict(runAt=r["run_at"], source=r["source_name"], processed=r["processed"],
                 success=r["success"], failed=r["failed"], error=r["error"])
            for r in con.execute("SELECT * FROM fetch_logs ORDER BY id DESC LIMIT 100")]
    last = con.execute("SELECT MAX(run_at) m FROM fetch_logs").fetchone()["m"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generatedAt": now_iso(), "lastRunAt": last, "categories": list(CATEGORIES),
        "articles": arts, "sources": sources, "logs": logs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"出力: {out} (記事 {len(arts)} 件)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    load_env_file()
    db_path = ROOT / os.environ.get("DB_PATH", "data/topics.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = dbm.connect(str(db_path))
    sync_sources(con)
    if not args.no_fetch:
        run_fetch(con, args.only)
    reclassify(con)
    export_json(con, ROOT / "web" / "public" / "data" / "articles.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
