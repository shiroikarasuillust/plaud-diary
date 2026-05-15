# Plaud日記自動生成 — セットアップ手順

毎日21時（JST）にPlaudの録音をまとめてGoogle Docsに日記として保存します。
PC不要・無料（GitHub ActionsとGoogle Cloudの無料枠で動作）。

---

## 必要なもの

| 項目 | 用途 |
|------|------|
| GitHubアカウント（無料） | スクリプトの保管・定時実行 |
| Anthropic APIキー | Claude で日記を生成 |
| Plaud トークン | 自分の録音データを取得 |
| Google Cloud プロジェクト | Google Docsへの書き込み |
| Google ドキュメント（日記用） | 日記の保存先 |

---

## Step 1：GitHubリポジトリを作る

1. https://github.com/new でリポジトリを新規作成
   - 名前例：`plaud-diary`
   - **Private**（非公開）を選択
   - `Add a README file` にチェック → **Create repository**

2. このフォルダの中身をリポジトリにアップロード
   - GitHub画面の「Add file → Upload files」から以下をドラッグ
     - `plaud_diary.py`
     - `requirements.txt`
     - `.github/workflows/diary.yml`

---

## Step 2：Plaud トークンを取得する（10分で完了）

1. ブラウザで https://web.plaud.ai にログイン
2. **F12** キー → 「Application」タブ → 左サイドバー「Local Storage」→ `https://web.plaud.ai`
3. キー一覧から `tokenstr` または `token` を探してその値をコピー
   - 値は `eyJ...` で始まる長い文字列（JWT）
   - ※見つからない場合：「Network」タブで任意のAPIリクエストを選択 → 「Headers」→ `Authorization: Bearer xxxxxx` の `xxxxxx` 部分をコピー

> このトークンは約300日（10ヶ月）有効です。期限が切れたら同じ手順で更新してください。

---

## Step 3：Google Docs APIのサービスアカウントを作る（20分）

### 3-1. Google Cloud プロジェクトを作成

1. https://console.cloud.google.com/ にアクセス（Googleアカウントでログイン）
2. 画面上部「プロジェクトを選択」→「新しいプロジェクト」
3. プロジェクト名：`plaud-diary`（任意） → **作成**

### 3-2. Google Docs API を有効化

1. 左メニュー「APIとサービス」→「APIとサービスを有効にする」
2. 検索欄に「Google Docs」→ **Google Docs API** を選択 → **有効にする**

### 3-3. サービスアカウントを作成

1. 左メニュー「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「サービスアカウント」
3. 名前：`diary-writer`（任意） → **作成して続行**
4. ロールは設定不要 → **完了**

### 3-4. JSONキーをダウンロード

1. 作成したサービスアカウントをクリック（メールアドレスが表示される）
2. 「キー」タブ → 「キーを追加」→「新しいキーを作成」→ **JSON** → **作成**
3. JSONファイルがダウンロードされる（例：`plaud-diary-xxxx.json`）
4. このJSONファイルの**全内容**をコピーしておく

### 3-5. Google ドキュメントをサービスアカウントと共有

1. Google ドキュメントで新規ドキュメントを作成（日記帳として使うもの）
   - タイトル例：「Plaud日記 2026」
2. 右上「共有」ボタン → 先ほど作ったサービスアカウントのメールアドレスを入力
   - メールアドレスは `diary-writer@plaud-diary-xxxx.iam.gserviceaccount.com` の形式（3-3で確認）
   - 権限：**編集者** → **送信**
3. ドキュメントのURLから**ドキュメントID**をコピー
   - URL例：`https://docs.google.com/document/d/`**`1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`**`/edit`
   - 太字部分がIDです

---

## Step 4：GitHubシークレットを登録する

1. GitHubのリポジトリ画面 → 「Settings」→「Secrets and variables」→「Actions」
2. **「New repository secret」** で以下の4つを登録：

| シークレット名 | 値 |
|---|---|
| `PLAUD_TOKEN` | Step 2 でコピーした `eyJ...` のトークン |
| `ANTHROPIC_API_KEY` | Anthropic コンソールの APIキー（`sk-ant-...`） |
| `GOOGLE_DOC_ID` | Step 3-5 でコピーしたドキュメントID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Step 3-4 でダウンロードしたJSONファイルの**全内容**をそのまま貼り付け |

---

## Step 5：動作確認（手動実行）

1. GitHubリポジトリ → 「Actions」タブ
2. 左サイドバー「毎日Plaud日記生成」→「Run workflow」ボタン
3. 実行ログを確認し、エラーがなければOK
4. Google ドキュメントに日記が書き込まれていることを確認

---

## 自動実行スケジュール

毎日 **21:00 JST**（= 12:00 UTC）に自動実行されます。
翌日の日記を見たいときは次の日にGoogle Docsを確認してください。

---

## トラブルシューティング

| エラー | 対処 |
|---|---|
| `PLAUD_TOKEN` 関連のエラー | トークンを再取得してシークレットを更新（Step 2） |
| `403 Forbidden` (Google Docs) | サービスアカウントとドキュメントの共有を確認（Step 3-5） |
| 録音が0件と表示される | その日にPlaudで録音があるか確認。または録音の`start_time`がJSTで当日かチェック |
| `ANTHROPIC_API_KEY` エラー | APIキーの有効性と残高を確認 |

---

## Plaudトークンの更新（約10ヶ月ごと）

1. https://web.plaud.ai にログイン
2. Step 2 と同じ手順でトークンを取得
3. GitHub シークレット `PLAUD_TOKEN` を更新
