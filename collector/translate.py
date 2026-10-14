"""英語タイトルの日本語化（MyMemory 無料API・キー不要）。

- 日本語を含むタイトルは翻訳しない。結果は articles.title_ja にキャッシュする。
- 無料枠の制限に達したら中断し、残りは次回実行で新しい記事から順に処理する。
- 失敗しても収集全体は止めない（原文タイトルを表示）。
"""
import json
import re
import time
import urllib.parse
import urllib.request

API = "https://api.mymemory.translated.net/get"
JA = re.compile(r"[぀-ヿ㐀-鿿]")
PER_RUN_LIMIT = 80


def needs_translation(title: str) -> bool:
    return bool(title) and not JA.search(title) and re.search(r"[A-Za-z]{3,}", title) is not None


def translate_text(text: str) -> str | None:
    q = urllib.parse.urlencode({"q": text[:400], "langpair": "en|ja"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "AITopicsBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8"))
    status = str(body.get("responseStatus"))
    out = (body.get("responseData") or {}).get("translatedText") or ""
    if status != "200" or "MYMEMORY WARNING" in out.upper() or "QUERY LENGTH LIMIT" in out.upper():
        raise RuntimeError(f"翻訳API制限/エラー: status={status} {out[:80]}")
    return out.strip() or None


def translate_missing(con, limit: int = PER_RUN_LIMIT) -> None:
    rows = con.execute(
        """SELECT id,title FROM articles WHERE title_ja IS NULL AND duplicate_of IS NULL
           ORDER BY COALESCE(published_at,fetched_at) DESC""").fetchall()
    todo = [r for r in rows if needs_translation(r["title"])][:limit]
    done = 0
    for r in todo:
        try:
            ja = translate_text(r["title"])
        except Exception as e:  # 上限到達・通信失敗は中断して次回に回す
            print(f"[翻訳] 中断: {type(e).__name__}: {e}")
            break
        if ja and JA.search(ja):
            con.execute("UPDATE articles SET title_ja=? WHERE id=?", (ja, r["id"]))
            done += 1
        time.sleep(0.5)
    con.commit()
    print(f"[翻訳] {done}/{len(todo)} 件（未翻訳の残り: {max(0, len([r for r in rows if needs_translation(r['title'])]) - done)} 件）")
