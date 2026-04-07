"""
チェックポイント管理
==================
各ステップの結果をJSONで保存・読み込みし、途中再開を可能にする。
"""

import json
from pathlib import Path
from agents.base import console
from rich.panel import Panel


CHECKPOINT_FILE = "checkpoint.json"


def save_checkpoint(project_dir: Path, step: int, data: dict):
    """ステップ完了時にチェックポイントを保存"""
    cp_path = project_dir / CHECKPOINT_FILE
    if cp_path.exists():
        checkpoint = json.loads(cp_path.read_text(encoding="utf-8"))
    else:
        checkpoint = {"completed_steps": [], "data": {}}

    checkpoint["completed_steps"].append(step)
    checkpoint["data"].update(data)
    checkpoint["last_step"] = step

    cp_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(project_dir: Path) -> dict | None:
    """チェックポイントを読み込み。なければNone。"""
    cp_path = project_dir / CHECKPOINT_FILE
    if not cp_path.exists():
        return None
    return json.loads(cp_path.read_text(encoding="utf-8"))


def find_latest_project(output_dir: Path) -> Path | None:
    """最新のプロジェクトフォルダを探す"""
    if not output_dir.exists():
        return None
    projects = sorted(output_dir.iterdir(), reverse=True)
    for p in projects:
        if p.is_dir() and (p / CHECKPOINT_FILE).exists():
            return p
    return None


def list_completed_projects(output_dir: Path) -> list[tuple[Path, dict]]:
    """完了済み（Step7まで終了）のプロジェクト一覧を返す"""
    if not output_dir.exists():
        return []
    completed = []
    for p in sorted(output_dir.iterdir(), reverse=True):
        if p.is_dir() and (p / CHECKPOINT_FILE).exists():
            cp = load_checkpoint(p)
            if cp and cp.get("last_step", 0) >= 7:
                completed.append((p, cp))
    return completed


def ask_import_past_results(output_dir: Path) -> dict:
    """過去の完了済みプロジェクトからステップ結果を取り込む"""
    from rich.prompt import Prompt, Confirm

    completed = list_completed_projects(output_dir)
    if not completed:
        return {}

    console.print()
    console.print(Panel(
        "[bold cyan]━━━ 過去プロジェクトからの結果流用 ━━━[/bold cyan]\n\n"
        "過去に完了したプロジェクトのリサーチ結果やWho/What分析を\n"
        "今回のプロジェクトに流用できます。\n"
        "流用したステップはスキップされ、時間とコストを節約できます。",
        border_style="cyan",
    ))
    console.print()

    for i, (path, cp) in enumerate(completed[:5]):  # 最新5件まで
        industry = cp["data"].get("industry", "?")
        product = cp["data"].get("product", "?")
        console.print(f"  [cyan]{i + 1}[/cyan]: {path.name}  ({industry} / {product})")
    console.print(f"  [cyan]0[/cyan]: 流用しない（全ステップ新規実行）")
    console.print()

    choice = Prompt.ask("[cyan]どのプロジェクトの結果を流用しますか？[/cyan]", default="0")
    if choice == "0":
        return {}

    idx = int(choice) - 1
    if idx < 0 or idx >= len(completed):
        return {}

    past_path, past_cp = completed[idx]
    past_data = past_cp["data"]

    STEP_NAMES = {
        "result1": "Step 1: Who/What深掘り",
        "result2": "Step 2: 競合LPリサーチ",
        "result3": "Step 3: 別業界LPリサーチ",
        "result4": "Step 4: 広告コンテキスト分析",
        "result5": "Step 5: ワイヤーフレーム提案",
    }

    imported = {}
    skip_steps = set()
    console.print()
    console.print("[bold]どのステップの結果を流用しますか？（流用したステップはスキップ）[/bold]")
    console.print()
    for key, name in STEP_NAMES.items():
        if past_data.get(key):
            preview = past_data[key][:100] + "..." if len(past_data.get(key, "")) > 100 else past_data.get(key, "")
            console.print(f"  {name}")
            console.print(f"  [dim]{preview}[/dim]")
            if Confirm.ask(f"  [cyan]{name} を流用する？[/cyan]", default=False):
                imported[key] = past_data[key]
                step_num = int(key.replace("result", ""))
                skip_steps.add(step_num)
            console.print()

    if imported:
        imported["_skip_steps"] = skip_steps
        console.print(f"[green]{len(skip_steps)}個のステップを流用します！[/green]\n")

    return imported


def ask_resume(output_dir: Path) -> tuple[Path | None, dict | None]:
    """途中再開するか聞く。再開する場合はproject_dirとcheckpointを返す。"""
    latest = find_latest_project(output_dir)
    if latest is None:
        return None, None

    checkpoint = load_checkpoint(latest)
    if checkpoint is None:
        return None, None

    last_step = checkpoint.get("last_step", 0)
    if last_step >= 7:  # 全ステップ完了済み
        return None, None

    console.print()
    console.print(f"[yellow]前回の途中データが見つかりました: {latest.name}[/yellow]")
    console.print(f"[yellow]完了済みステップ: Step {last_step} まで[/yellow]")
    console.print()

    from rich.prompt import Confirm
    resume = Confirm.ask("[yellow]途中から再開しますか？（Noで新規作成）[/yellow]")

    if resume:
        return latest, checkpoint
    return None, None
