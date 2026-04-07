"""
YAML設定ファイルの読み込み
========================
input.yaml を読み込んで、gather_inputs() と同じ形の dict を返す。
"""

import sys
from pathlib import Path

import yaml


REQUIRED_FIELDS = [
    "lp_purpose",
    "industry",
    "product",
    "competitor_url",
    "cross_industry_url",
    "who",
    "what",
]


def load_config(config_path: str) -> dict:
    """YAMLファイルを読み込み、バリデーションして inputs dict を返す"""
    path = Path(config_path)
    if not path.exists():
        print(f"エラー: 設定ファイルが見つかりません: {config_path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        print(f"エラー: 設定ファイルの形式が不正です: {config_path}")
        sys.exit(1)

    # 必須フィールドチェック
    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        print(f"エラー: 以下の必須フィールドがありません: {', '.join(missing)}")
        print(f"設定ファイル: {config_path}")
        sys.exit(1)

    # gather_inputs() と同じ形にフォーマット
    lp_purpose = raw["lp_purpose"].strip()
    who_text = raw["who"].strip()
    what_text = raw["what"].strip()

    who = f"【LP目的】{lp_purpose}\n\n【ターゲット情報（オーナー自由記述）】\n{who_text}"
    what = f"【提供価値（オーナー自由記述）】\n{what_text}"

    meta_ad_info = raw.get("meta_ad_info", "").strip()
    if meta_ad_info:
        ad_info_pre = f"## Meta広告（Facebook/Instagram）\n{meta_ad_info}"
    else:
        ad_info_pre = ""

    return {
        "lp_purpose": lp_purpose,
        "industry": raw["industry"].strip(),
        "product": raw["product"].strip(),
        "competitor_url": raw["competitor_url"].strip(),
        "cross_industry_url": raw["cross_industry_url"].strip(),
        "who": who,
        "what": what,
        "ad_info_pre": ad_info_pre,
    }
