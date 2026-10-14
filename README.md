# AI・SIトピックス

AI・SI・製造業DXの最新情報をRSS等から毎日自動収集し、分類して日本語UIで一覧表示するWebアプリです。
ブラウザを閉じていても GitHub Actions（サーバー側スケジューラー）が1日1回収集します。

## 構成

```
collector/   収集（Python 3.11 標準ライブラリのみ。追加インストール不要）
  sources.json  情報取得元（追加・無効化はここを編集）
  collect.py    取得 → SQLite保存 → web/public/data/articles.json 出力
  classify.py   規則ベースのカテゴリ分類・重要度判定
data/topics.db  SQLite（articles / sources / categories / fetch_logs）
web/         表示（React + TypeScript + Vite、スマホ対応の静的サイト）
.github/workflows/collect.yml  定期実行 + GitHub Pages 配信
```

データの流れ: RSS → `collect.py` → SQLite → 静的JSON → ブラウザ。収集・保存・表示は分離されています。

## ローカルでの起動

```bash
# 1. 収集（APIキー不要）
python collector/collect.py            # 全ソース取得（手動更新）
python collector/collect.py --only zenn-ai   # 1ソースだけ
python collector/collect.py --no-fetch       # JSONの再出力のみ

# 2. 表示
cd web
npm install
npm run dev        # 開発サーバー
npm run build      # 本番ビルド（web/dist）
```

## 定期実行・公開（GitHub Actions + GitHub Pages）

1. このフォルダを GitHub リポジトリに push する。
2. リポジトリの Settings → Pages → Source を **GitHub Actions** にする。
3. `.github/workflows/collect.yml` が毎日 日本時間 06:00 に収集・DB更新・サイト公開を行う。
4. 手動更新: Actions タブ → `collect-and-deploy` → **Run workflow**。

## 設定

| 項目 | 変更方法 |
|---|---|
| 情報取得元 | `collector/sources.json`（`enabled`, `priority`） |
| カテゴリ・キーワード・重要度判定 | `collector/classify.py` |
| 取得頻度 | `collect.yml` の `cron`（GitHub Actions 側で管理。画面からは変更不可） |
| 保持期間 | `collect.py` の `EXPORT_DAYS`（既定120日） |
| 表示件数・お気に入り | 画面の設定（端末のブラウザ内に保存） |

環境変数（`.env.example` 参照、`.env` は Git 管理外）:
`ANTHROPIC_API_KEY`（任意・AI要約は未実装/第3段階）、`DB_PATH`。
GitHub では Secrets に登録し、コードには書かないでください。

## 仕様上のポイント

- 記事URLは正規化（utmなど除去・フラグメント除去）し、`url_normalized` のUNIQUE制約で重複登録を防止。同一タイトルの転載は `duplicate_of` で検知し一覧から除外。
- 取得失敗は `fetch_logs` と `sources.last_error` に記録し、次のソースの処理を継続。画面の取得履歴・警告バナーで確認可能。
- 最終取得から48時間超で「情報が古い可能性」を表示。時刻は日本時間表示、公開日時と取得日時は別管理。
- 概要はフィードの抜粋であり、AI要約ではありません（画面に明記）。取得できない場合は推測せず「取得できませんでした」と表示。
- 取得元はRSS/Atomのみ。スクレイピングはしません。

## 未実装（今後の段階）

AI（LLM）要約・業務活用ポイント生成（第3段階）、CSV出力・メール通知・ユーザー別設定（第4段階）。
