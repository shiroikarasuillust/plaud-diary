#!/usr/bin/env python3
"""
Plaud日記自動生成スクリプト
毎日21時（JST）にGitHub Actionsで実行し、
当日のPlaud録音をClaudeでまとめてGoogle Docsに日記として保存する。
"""

import os
import json
import datetime
import zoneinfo
import sys
import requests
import anthropic
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── 定数 ────────────────────────────────────────────────────
JST = zoneinfo.ZoneInfo("Asia/Tokyo")
PLAUD_BASE_URL = "https://api.plaud.ai"
ANTHROPIC_MODEL = "claude-sonnet-4-6"


# ── Plaud API ────────────────────────────────────────────────

def plaud_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def fetch_today_recordings(token: str, target_date: datetime.date) -> list[dict]:
    """当日の録音ファイル一覧を返す"""
    resp = requests.get(
        f"{PLAUD_BASE_URL}/file/simple/web",
        params={"skip": 0, "limit": 100, "is_trash": 0, "sort_by": "start_time", "is_desc": "true"},
        headers=plaud_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    # レスポンス構造は data_files または data.files の場合がある
    files = (
        payload.get("data_files")
        or payload.get("data", {}).get("files")
        or []
    )

    result = []
    for f in files:
        ts = f.get("start_time") or f.get("create_time") or 0
        if ts > 1e10:   # ミリ秒 → 秒
            ts /= 1000
        if ts == 0:
            continue
        file_date = datetime.datetime.fromtimestamp(ts, tz=JST).date()
        if file_date == target_date:
            result.append(f)

    return result


def fetch_transcript(token: str, file_id: str) -> str:
    """ファイル詳細から文字起こしテキストを取得する"""
    resp = requests.get(
        f"{PLAUD_BASE_URL}/file/detail/{file_id}",
        headers=plaud_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})

    # ① segments 形式（話者ラベル付き）
    segments = (
        data.get("trans_result", {}).get("segments")
        or data.get("segments")
        or []
    )
    if segments:
        return "\n".join(
            f"[{s.get('speaker', '').strip() or '話者'}] {s.get('text', '').strip()}"
            for s in segments
            if s.get("text")
        )

    # ② フラットなテキスト
    for key in ("trans_text", "transcript", "transcription", "text"):
        val = data.get(key, "").strip()
        if val:
            return val

    # ③ AIサマリーで代用
    for key in ("summary", "ai_summary"):
        val = (data.get(key) or data.get("ai_result", {}).get(key, "")).strip()
        if val:
            return f"[サマリー] {val}"

    return ""


# ── Claude API ───────────────────────────────────────────────

def generate_diary(items: list[dict], target_date: datetime.date) -> str:
    """文字起こしリストから日記を生成する"""
    date_str = target_date.strftime("%Y年%m月%d日")

    if not items or all(not i["transcript"] for i in items):
        return f"（{date_str}の録音データはありませんでした）"

    body = ""
    for i, item in enumerate(items, 1):
        if item["transcript"]:
            body += f"\n\n【録音{i}：{item['filename']}】\n{item['transcript']}"

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                f"以下は{date_str}の音声録音の文字起こしです。\n"
                "これらをもとに、その日の出来事・考え・気づきをまとめた日記を書いてください。\n\n"
                "【形式】\n"
                f"- {date_str}付けの日記\n"
                "- 自然な日本語・一人称（「私は」など）\n"
                "- 重要なポイントを整理して読みやすく\n"
                "- 400〜800字程度\n\n"
                f"【文字起こし】{body}"
            ),
        }],
    )
    return msg.content[0].text


# ── Google Docs API ──────────────────────────────────────────

def append_to_google_doc(
    service_account_info: dict, doc_id: str, date: datetime.date, diary_text: str
) -> None:
    """Google Docsの末尾に日記エントリを追記する"""
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/documents"],
    )
    svc = build("docs", "v1", credentials=creds)

    doc = svc.documents().get(documentId=doc_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1

    date_str = date.strftime("%Y年%m月%d日")
    separator = "=" * 40
    text = f"\n\n{separator}\n{date_str}\n{separator}\n{diary_text}\n"

    svc.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text}}]},
    ).execute()
    print(f"Google Docs（{doc_id}）に保存しました")


# ── メイン ───────────────────────────────────────────────────

def main() -> None:
    # 環境変数から読み込み
    plaud_token = os.environ["PLAUD_TOKEN"]
    google_doc_id = os.environ["GOOGLE_DOC_ID"]
    google_creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

    service_account_info = json.loads(google_creds_json)

    today, now = datetime.date.today(), datetime.datetime.now(JST)
    # GitHub ActionsはUTC実行なのでJST日付に変換
    today = datetime.datetime.now(JST).date()
    print(f"処理日付: {today}  現在時刻: {now.strftime('%H:%M JST')}")

    # Step 1: 録音一覧
    print("Plaudから録音を取得中...")
    recordings = fetch_today_recordings(plaud_token, today)
    print(f"  → {len(recordings)} 件の録音が見つかりました")

    # Step 2: 文字起こし取得
    items = []
    for rec in recordings:
        file_id = rec.get("file_id") or rec.get("id") or rec.get("file_url", "")
        filename = rec.get("filename") or rec.get("name") or file_id
        print(f"  文字起こし取得: {filename}")
        try:
            transcript = fetch_transcript(plaud_token, file_id)
        except Exception as e:
            print(f"  ⚠ 取得失敗（スキップ）: {e}")
            transcript = ""
        items.append({"filename": filename, "transcript": transcript})

    # Step 3: 日記生成
    print("Claude で日記を生成中...")
    diary = generate_diary(items, today)
    print("---- 生成された日記 ----")
    print(diary)
    print("------------------------")

    # Step 4: Google Docs 保存
    print("Google Docs に保存中...")
    append_to_google_doc(service_account_info, google_doc_id, today, diary)
    print("完了！")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"[ERROR] 環境変数が設定されていません: {e}", file=sys.stderr)
        sys.exit(1)
