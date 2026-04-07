"""
ナレッジDB（案件を超えた学習の蓄積）
====================================
プロジェクト完了時に学びを自動抽出し、次回以降に活用する。
業界別・訴求別の知見が溜まっていく仕組み。
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import call_claude, console
from rich.panel import Panel

KNOWLEDGE_FILE = "knowledge_db.json"


def _get_db_path() -> Path:
    """ナレッジDBのパスを返す（output/の直下）"""
    return Path(__file__).parent.parent / "output" / KNOWLEDGE_FILE


def load_knowledge() -> list[dict]:
    """ナレッジDBを読み込み"""
    db_path = _get_db_path()
    if not db_path.exists():
        return []
    return json.loads(db_path.read_text(encoding="utf-8"))


def save_knowledge(entries: list[dict]):
    """ナレッジDBを保存"""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_learnings(results: dict, industry: str, product: str) -> dict:
    """プロジェクト完了時に、AIが学びを自動抽出する"""
    console.print()
    console.print(Panel(
        "[bold green]📚 ナレッジ抽出中...[/bold green]\n"
        "今回のプロジェクトから、次回以降に使える学びを自動抽出しています",
        border_style="green",
    ))

    # 結論サマリーとWho/Whatから知見を抽出
    summary = results.get("summary", "")
    who_what = results.get("result1", "")

    system = (
        "あなたはLP制作の知見を抽出するアナリストです。\n"
        "今回のLP制作プロジェクトの結果から、次回以降に使える学びを抽出してください。\n"
        "出力は必ず以下のJSON形式で。日本語で。\n"
    )

    prompt = (
        f"## 業界: {industry}\n## 商材: {product}\n\n"
        f"## Who/What分析結果\n{who_what[:3000]}\n\n"
        f"## ディスカッション結論サマリー\n{summary[:3000]}\n\n"
        "---\n\n"
        "以下のJSON形式で学びを抽出してください（```jsonで囲んでください）：\n\n"
        "```json\n"
        "{\n"
        '  "industry": "業界名",\n'
        '  "product": "商材名",\n'
        '  "target_insight": "この業界のターゲットについて分かったこと（1-2文）",\n'
        '  "winning_pattern": "効果的だった訴求パターン・LP型（1-2文）",\n'
        '  "framework_break": "フレームワーク破壊で有効だったこと（あれば）",\n'
        '  "pitfall": "次回避けるべき落とし穴（あれば）",\n'
        '  "reusable_copy": "再利用できそうなコピーの切り口（あれば）"\n'
        "}\n"
        "```\n"
    )

    raw = call_claude(system, prompt, use_web_search=False, max_tokens=2000)

    # JSONを抽出
    try:
        json_start = raw.index("{")
        json_end = raw.rindex("}") + 1
        learning = json.loads(raw[json_start:json_end])
    except (ValueError, json.JSONDecodeError):
        learning = {
            "industry": industry,
            "product": product,
            "target_insight": "（自動抽出失敗）",
            "winning_pattern": "（自動抽出失敗）",
        }

    learning["extracted_at"] = datetime.now().isoformat()
    return learning


def save_project_learning(results: dict, industry: str, product: str):
    """プロジェクト完了時に学びを抽出してDBに保存"""
    learning = extract_learnings(results, industry, product)

    db = load_knowledge()
    db.append(learning)
    save_knowledge(db)

    console.print()
    console.print(Panel(
        f"[bold green]📚 ナレッジを保存しました！[/bold green]\n\n"
        f"業界: {learning.get('industry', '?')}\n"
        f"ターゲット知見: {learning.get('target_insight', '-')}\n"
        f"勝ちパターン: {learning.get('winning_pattern', '-')}\n"
        f"フレームワーク破壊: {learning.get('framework_break', '-')}\n\n"
        f"[dim]累計 {len(db)} 件のナレッジが蓄積されています[/dim]",
        border_style="green",
    ))


def get_relevant_knowledge(industry: str) -> str:
    """指定業界に関連するナレッジを検索して文字列で返す"""
    db = load_knowledge()
    if not db:
        return ""

    relevant = [e for e in db if e.get("industry", "") == industry]
    # 同業界がなければ全件から最新3件
    if not relevant:
        relevant = db[-3:]
        header = "（同業界のナレッジなし。他業界の最新知見を参考表示）"
    else:
        header = f"（{industry}業界の過去ナレッジ {len(relevant)}件）"

    lines = [f"## 過去のナレッジDB {header}\n"]
    for e in relevant[-5:]:  # 最新5件まで
        lines.append(
            f"### {e.get('industry', '?')} / {e.get('product', '?')} ({e.get('extracted_at', '?')[:10]})\n"
            f"- ターゲット知見: {e.get('target_insight', '-')}\n"
            f"- 勝ちパターン: {e.get('winning_pattern', '-')}\n"
            f"- フレームワーク破壊: {e.get('framework_break', '-')}\n"
            f"- 落とし穴: {e.get('pitfall', '-')}\n"
            f"- 再利用コピー: {e.get('reusable_copy', '-')}\n"
        )

    return "\n".join(lines)
