"""
CLI引数パーサー
==============
--config を渡すと非対話（バッチ）モードで動く。
引数なしなら従来の対話モード。
"""

import argparse


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="LP制作エージェント — 対話モード / バッチモード両対応",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="YAML設定ファイルのパス（指定すると非対話モード）",
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=range(1, 8),
        help="指定したステップだけ実行（1〜7）",
    )
    parser.add_argument(
        "--from-step",
        type=int,
        choices=range(1, 8),
        help="指定したステップから最後まで実行（1〜7）",
    )
    parser.add_argument(
        "--revise",
        type=int,
        choices=range(1, 8),
        help="指定ステップの結果を修正（--feedback, --project-dir 必須）",
    )
    parser.add_argument(
        "--feedback",
        type=str,
        help="修正フィードバック（--revise と一緒に使う）",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        help="既存プロジェクトディレクトリ（途中再開・修正時に使う）",
    )

    args = parser.parse_args(argv)

    # バリデーション
    if args.revise is not None:
        if not args.feedback:
            parser.error("--revise には --feedback が必要です")
        if not args.project_dir:
            parser.error("--revise には --project-dir が必要です")

    if args.step and args.from_step:
        parser.error("--step と --from-step は同時に使えません")

    if (args.step or args.from_step) and not args.config and not args.project_dir:
        parser.error("--step / --from-step には --config か --project-dir が必要です")

    return args
