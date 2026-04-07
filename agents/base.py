"""
共通ベースモジュール
==================
全エージェントが使うClaude API呼び出し・ファイル読み込み・確認機能
"""

import base64
import io
import os
from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

console = Console()

# APIキー取得
_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
try:
    import streamlit as st
    _api_key = st.secrets.get("ANTHROPIC_API_KEY", _api_key)
except Exception:
    pass
_api_key = str(_api_key).strip()


def get_client() -> anthropic.Anthropic:
    """APIクライアントを取得"""
    if _api_key:
        return anthropic.Anthropic(api_key=_api_key)
    return anthropic.Anthropic()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MODEL = "claude-sonnet-4-20250514"

# ── バッチモード（非対話） ──
_batch_mode = False


def set_batch_mode(enabled: bool):
    global _batch_mode
    _batch_mode = enabled


def is_batch_mode() -> bool:
    return _batch_mode


def save_unresolved_flags(flags: list[str], step_name: str, project_dir: Path, gate_type: str = "confirm"):
    """未解決フラグをファイルに保存（バッチモード用）"""
    flags_file = project_dir / "unresolved_flags.md"
    with open(flags_file, "a", encoding="utf-8") as f:
        f.write(f"\n## {step_name} ({gate_type})\n")
        for flag in flags:
            f.write(f"- {flag}\n")
    console.print(f"[yellow][batch] {len(flags)}件の未解決フラグを unresolved_flags.md に保存[/yellow]")


def load_prompt(filename: str) -> str:
    """prompts/ からテンプレートを読み込む"""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def resize_image(image_bytes: bytes, max_pixels: int = 1568) -> tuple[bytes, str]:
    """大きい画像をリサイズしてJPEG圧縮。(bytes, media_type) を返す"""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    # RGBA → RGB変換（JPEG保存用）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 長辺がmax_pixelsを超えたらリサイズ
    w, h = img.size
    if max(w, h) > max_pixels:
        ratio = max_pixels / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue(), "image/jpeg"


def _build_content_with_images(user_message: str, images: list[bytes] | None = None) -> list[dict] | str:
    """テキスト + 画像をClaude APIのcontent形式に変換"""
    if not images:
        return user_message

    content = []
    for img_bytes in images:
        resized, media_type = resize_image(img_bytes)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(resized).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": user_message})
    return content


def call_claude(
    system_prompt: str,
    user_message: str,
    use_web_search: bool = False,
    max_tokens: int = 16000,
    images: list[bytes] | None = None,
) -> str:
    """Claude APIを呼び出す（Web検索ツール付き・画像対応）"""
    content = _build_content_with_images(user_message, images)
    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }

    if use_web_search:
        kwargs["tools"] = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 10,
            }
        ]

    all_text = []
    response = get_client().messages.create(**kwargs)

    while response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "text":
                all_text.append(block.text)

        kwargs["messages"] = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": [{"type": "text", "text": "続けてください。"}]},
        ]
        response = get_client().messages.create(**kwargs)

    for block in response.content:
        if block.type == "text":
            all_text.append(block.text)

    return "\n".join(all_text)


class GoBackRequest(Exception):
    """ユーザーが前のステップに戻りたい時に送出する例外"""
    def __init__(self, target_step: int):
        self.target_step = target_step


# ステップ別ジャッジガイド（おじんでんの判断力を育てる）
JUDGE_GUIDES = {
    1: (
        "📋 事実確認: Who/What深掘り（設計ブリーフ）\n"
        "以下の事実を確認してください：\n"
        "  ✅ ペルソナの属性・悩み・理想像は、実在のお客さんと合ってるか？\n"
        "  ✅ 「core complex（核心の痛み）」は事実か？お客さんから実際に聞いたことがあるか？\n"
        "  ✅ 実績数字・導入事例など、事実として使える根拠に漏れがないか？\n"
        "  ✅ 「骨格（一文）」に含まれる約束（promise）は、実際に提供できるものか？\n"
        "  ⚠️ 「いい感じ」かどうかではなく「事実として正しいか」をチェック"
    ),
    2: (
        "📋 事実確認: 競合LPリサーチ\n"
        "以下の事実を確認してください：\n"
        "  ✅ 分析された競合LPは実際に自社の競合か？的外れなLP分析が混じってないか？\n"
        "  ✅ 「業界の盲点」は本当に盲点か？実はもうやってるのに拾われてないだけでは？\n"
        "  ✅ 主要な競合で漏れているものがないか？（「あのLP入ってないやん」がないか）\n"
        "  ⚠️ リサーチ結果が自社の市場認識と合ってるかを事実ベースで確認"
    ),
    3: (
        "📋 事実確認: 別業界LPリサーチ\n"
        "以下の事実を確認してください：\n"
        "  ✅ 転用アイデアが自社の顧客層に合うか？（業界の常識に反してないか）\n"
        "  ✅ 転用する場合、自社で実現できるか？（リソース・体制の制約）\n"
        "  ✅ 「面白い」と「使える」は違う。実装可能なアイデアに絞れているか？\n"
        "  ⚠️ 事実として自社で実行できないアイデアに引っ張られてないか確認"
    ),
    4: (
        "📋 判断ガイド: Meta広告コンテキスト分析\n"
        "以下の事実を確認してください：\n"
        "  ✅ 自社のMeta広告で実際に効果が出てる表現が正しく拾われているか？\n"
        "  ✅ 広告クリエイティブ→LPの着地体験が具体的に設計されているか？\n"
        "  ✅ 「なぜ効いているか」の分析に納得できるか？\n"
        "  ✅ LP設計への提言が具体的で使えるレベルか？\n"
        "  ⚠️ 広告情報が薄い場合、分析も薄くなる。追加情報が必要なら「修正」を"
    ),
    5: (
        "📋 事実確認: ワイヤーフレーム提案\n"
        "以下の事実を確認してください：\n"
        "  ✅ 本命案と対抗案の違いは明確か？（似てたらムダ）\n"
        "  ✅ ヘッドコピーに含まれる数字・実績は事実か？\n"
        "  ✅ お客様の声・証拠セクションに使う素材は実際にあるか？\n"
        "  ✅ CTAで約束してること（無料相談、資料DL等）は本当に提供できるか？\n"
        "  ✅ 主要な反論（お客さんが「でも...」と思うこと）が3つ漏れなく潰されてるか？\n"
        "  ⚠️ 「刺さるかどうか」はおじんでんが判断。ここでは事実の漏れ・嘘がないか確認"
    ),
    7: (
        "📋 事実確認: 最終ワイヤーフレーム\n"
        "以下の事実を確認してください：\n"
        "  ✅ LP目的（最初に設定したもの）に対して、CTAが直結してるか？\n"
        "  ✅ ディスカッションで「必須修正」とされた項目が全て反映されてるか？\n"
        "  ✅ このワイヤーを制作会社に渡して、指示が曖昧な箇所がないか？\n"
        "  ✅ 使ってる数字・実績・権威性の根拠は全て事実か？\n"
        "  ⚠️ 完璧じゃなくていい。「これで出して、反応見て直す」覚悟があるかどうか"
    ),
}


def confirm_step(step_name: str, result: str, current_step: int = 0) -> str:
    """ステップ完了後にユーザーに確認。フィードバックがあれば返す。戻りたい場合はGoBackRequestを送出。"""
    if _batch_mode:
        console.print(f"[dim][batch] {step_name} — 完了（自動承認）[/dim]")
        return ""

    console.print()
    preview = result[:3000] + "\n\n...(続きはファイルに保存済み)" if len(result) > 3000 else result
    console.print(Panel(Markdown(preview), title=f"{step_name} 結果プレビュー", border_style="dim"))

    # 判断ガイドを表示（おじんでんの目を育てる）
    if current_step in JUDGE_GUIDES:
        console.print()
        console.print(Panel(JUDGE_GUIDES[current_step], border_style="yellow", title="🎯 ここを見てジャッジ"))

    console.print()

    choice = Prompt.ask(
        f"[bold]{step_name}[/bold]",
        choices=["ok", "修正", "戻る"],
        default="ok",
    )

    if choice == "ok":
        return ""
    elif choice == "戻る":
        if current_step <= 1:
            console.print("[dim]Step 1より前には戻れません。修正で対応してください。[/dim]")
            feedback = Prompt.ask("[yellow]修正・追加してほしいことを教えてください[/yellow]")
            return feedback
        console.print()
        console.print("[bold]━━━ どのステップに戻りますか？ ━━━[/bold]")
        step_names = {
            1: "Step 1: Who/What深掘り",
            2: "Step 2: 競合LPリサーチ",
            3: "Step 3: 別業界LPリサーチ",
            4: "Step 4: 広告コンテキスト分析",
            5: "Step 5: ワイヤーフレーム提案",
            6: "Step 6: ディスカッション",
        }
        for s in range(1, current_step):
            console.print(f"  [cyan]{s}[/cyan]: {step_names.get(s, f'Step {s}')}")
        target = Prompt.ask("[cyan]戻り先のStep番号[/cyan]", default=str(current_step - 1))
        raise GoBackRequest(int(target))
    else:
        feedback = Prompt.ask("[yellow]修正・追加してほしいことを教えてください[/yellow]")
        return feedback


def revise_with_feedback(
    system_prompt: str,
    original_result: str,
    feedback: str,
    use_web_search: bool = False,
    max_tokens: int = 16000,
) -> str:
    """フィードバックを反映して再生成"""
    console.print("[dim]フィードバックを反映して再生成中...[/dim]")
    user_message = (
        f"以下は前回の出力結果です:\n\n{original_result}\n\n"
        f"---\n\n"
        f"以下のフィードバックを反映して、改善版を出力してください:\n\n{feedback}"
    )
    return call_claude(system_prompt, user_message, use_web_search=use_web_search, max_tokens=max_tokens)


def save_output(filename: str, content: str, project_dir: Path) -> Path:
    """成果物をoutput/に保存"""
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / filename
    path.write_text(content, encoding="utf-8")
    return path
