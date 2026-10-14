"""規則ベースの分類・重要度判定・活用ポイント付与（APIキー不要）。
記事内の文章は命令として扱わず、キーワード照合のみ行う。基準は rules.json で管理する。"""
import json
import re
from pathlib import Path

RULES = json.loads((Path(__file__).parent / "rules.json").read_text(encoding="utf-8"))
CATEGORY_KEYWORDS = RULES["category_keywords"]
IMPORTANT_WORDS = RULES["important_words"]
THRESHOLDS = RULES["importance_thresholds"]
USAGE_POINTS = RULES["usage_points"]

_SHORT_ASCII = re.compile(r"^[a-z0-9 .\-]+$")


def _hit(text: str, kw: str) -> bool:
    if _SHORT_ASCII.match(kw) and len(kw) <= 4:  # "ai" や "api" の部分一致を避ける
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text) is not None
    return kw in text


def classify(title: str, summary: str, source_name: str = "") -> tuple[list[str], list[str]]:
    text = f"{title} {summary} {source_name}".lower()
    cats, kws = [], []
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = [w for w in words if _hit(text, w)]
        if hits:
            cats.append(cat)
            kws.extend(h for h in hits if h not in kws)
    return (cats or ["その他"]), kws[:8]


def importance(title: str, summary: str, categories: list[str], source_priority: int) -> int:
    """3=高 / 2=中 / 1=低。ソース優先度・重要語・カテゴリ該当から算出。"""
    text = f"{title} {summary}".lower()
    score = source_priority
    score += min(2, sum(1 for w in IMPORTANT_WORDS if w in text))
    if "その他" not in categories:
        score += 1
    return 3 if score >= THRESHOLDS["high"] else 2 if score >= THRESHOLDS["medium"] else 1


def usage_points(categories: list[str]) -> str | None:
    """カテゴリに基づく着眼点（記事内容の要約ではなく、規則による目安）。"""
    texts = [USAGE_POINTS[c][0] for c in categories if c in USAGE_POINTS][:2]
    return "\n".join(texts) or None
