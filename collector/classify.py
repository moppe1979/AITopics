"""規則ベースの分類・重要度判定（APIキー不要）。記事内の文章は命令として扱わず、キーワード照合のみ行う。"""
import re

CATEGORY_KEYWORDS = {
    "AI": ["ai", "生成ai", "llm", "chatgpt", "openai", "claude", "anthropic", "gemini", "gpt", "rag",
           "機械学習", "人工知能", "ocr", "音声認識", "画像認識", "copilot", "machine learning"],
    "AIエージェント": ["エージェント", "agent", "agentic", "claude code", "自律", "mcp", "codex"],
    "SI・システム開発": ["システム開発", "システム連携", "web api", "webアプリ", "業務アプリ", "インテグレーション",
                  "api", "sdk", "typescript", "python", "github", "オープンソース", "open source", "dx", "devops"],
    "クラウド・インフラ": ["クラウド", "cloud", "azure", "aws", "サーバー", "ネットワーク", "kubernetes", "docker", "microsoft 365", "インフラ"],
    "データベース・データ連携": ["データベース", "database", "sql", "データ連携", "dataverse", "ベクトル", "vector", "postgres", "etl", "データ基盤"],
    "ローコード・業務自動化": ["power apps", "power automate", "power bi", "power platform", "ローコード", "ノーコード",
                     "low-code", "no-code", "rpa", "業務自動化", "sharepoint", "業務改善"],
    "セキュリティ": ["セキュリティ", "security", "脆弱性", "vulnerability", "cve", "ランサム", "ransomware", "マルウェア", "不正アクセス", "サイバー"],
    "製造業・IoT": ["製造", "工場", "スマートファクトリー", "iot", "センサー", "生産管理", "品質管理", "設備保全",
                 "画像検査", "異常検知", "manufactur", "factory", "予知保全", "monoist"],
}
IMPORTANT_WORDS = ["発表", "リリース", "公開", "新機能", "料金", "価格", "脆弱性", "緊急", "重大",
                   "launch", "release", "announce", "pricing", "critical", "vulnerability"]

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
    return 3 if score >= 5 else 2 if score >= 3 else 1
