#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Any, Optional, List

"""rsyncを使用したGUIバックアップツール。

このモジュールは、指定されたバックアップ元ディレクトリからバックアップ先ディレクトリへ
rsyncコマンドを用いて同期を行います。実行前にrsyncのドライラン(-avhin)を用いて
正確な対象ファイル数を取得し、ユーザーの確認を経てから進捗を表示しながら実行します。

主な機能:
    - 指定サイズ以上のファイル除外
    - 特定の拡張子の除外
    - rsync -avhi による正確なファイル転送数カウント
    - 全ファイル数に対する累積進捗率の表示
    - tkinterによるリアルタイム進捗表示と中断機能

Requires:
    - Python 3.x
    - rsync

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/05/01)
    1.0.1 (2026/05/01) - ディレクトリ存在チェック機能を追加
    2.0.0 (2026/05/04) - プレビュー機能, ログ閲覧機能, class PreviewDialog
    3.0.0 (2026/06/14) - JSON形式の設定ファイル(.rsync_backup_python.json)からの読み込み機能を追加
    3.1.0 (2026/06/28) - FLAG_SIZE_ONLY(タイムスタンプの相違を無視),FLAG_USE_SUFFIX(旧ファイルを同一階層にバックアップ)の機能追加
"""

# ==========================================
# 設定: グローバル変数
# ==========================================
# コピー元, コピー先 ディレクトリ (初期値はダミー値)
BACKUP_SOURCE_DIR: str = "/tmp/test/src/"
BACKUP_DESTINATION_DIR: str = "/tmp/test/dst/"
# 除外サイズ(このサイズ以上のファイルは対象外。rsyncの--max-sizeに対応)
EXCLUDE_FILESIZE_MB: int = 10
# 除外拡張子(カンマ区切りで複数指定可。rsyncの--excludeスイッチに対応)
EXCLUDE_FILE_EXTENSION: str = "bak,tmp"
# デバッグ用に表示を遅くする
FLAG_DEBUG_WAIT: bool = True
# ファイルの転送条件はファイルサイズのみ(日時などは判定対象外。rsyncの--size-onlyスイッチに対応)
FLAG_SIZE_ONLY: bool = False
# ファイルが上書きされる前に同一階層にバックアップを行う(rsyncの--backup --suffix=#####に対応)
FLAG_USE_SUFFIX: bool = False
# 同一階層に作られるバックアップファイルの命名規則
BACKUP_SUFFIX_STR: str = "_bak%Y%m%d"
# ファイルの転送条件はチェックサム(rsyncの--checksumに対応)
FLAG_CHECKSUM: bool = False

# ==========================================
# JSON設定ファイルの読み込み処理 (Ver3.0 新規追加)
# ==========================================
CONFIG_FILE_NAME = ".rsync_backup_python.json"
# ユーザーのホームディレクトリのパスを取得
CONFIG_PATH = os.path.join(os.path.expanduser("~"), CONFIG_FILE_NAME)


def _get_itemize_legend(cmd_str: str) -> str:
    """プレビューおよび結果ログの先頭に付与する、共通のコマンド表記と凡例テキストを生成します。

    Args:
        cmd_str (str): 画面に表示・コピペ用として結合されたrsyncのフルコマンド文字列。

    Returns:
        str: コマンド情報と、各カラムの記号の意味を日本語化した凡例ブロックのテキスト。
    """
    return (
        f"■ 実行したrsyncコマンド (端末コピペ用):\n"
        f"{cmd_str}\n"
        f"======================================================================\n\n"
        "※itemize-changes凡例\n"
        "==============\n"
        "【左端1文字目: 動向】\n"
        "  > : ファイルを転送先へコピー (追加または上書き)\n"
        "  c : 転送先にディレクトリ等を新規作成\n"
        "  . : 変更（転送）なし\n"
        "【左端2文字目: 種類】\n"
        "  f : 通常のファイル\n"
        "  d : ディレクトリ\n"
        "【それ以降の文字: 変更理由（一部抜粋）】\n"
        "  + : 新規ファイル（初回転送）\n"
        "  s : ファイルサイズが異なる\n"
        "  t : タイムスタンプ（更新時刻）が異なる\n"
        "  c : チェックサムが異なる(--checksumスイッチ指定の場合のみ)\n"
        "  p : 属性（permission）が異なる\n"
        "  . : 変更なし\n"
        "======================================================================\n\n"
    )


def validate_and_sanitize_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """JSONから読み込んだ設定データの汚染除去（サニタイズ）と妥当性検証を行います。

    悪意ある手動編集などでデータが汚染されていた場合、ここで無毒化するか、
    致命的な場合は例外（ValueError）を発生させて安全にスクリプトを終了させます。

    Args:
        raw_config (dict[str, Any]): JSONファイルから読み込んだ生のデータ。

    Returns:
        dict[str, Any]: 完全にクリーンアップされ、型が保証された設定データ。

    Raises:
        ValueError: 必須項目の欠落、または回復不能な不正データ（マイナスの値など）がある場合。
    """
    sanitized: dict[str, Any] = {}

    # --- 1. 必須キーの存在チェック ---
    # ※過去互換性を維持するため、新フラグ(FLAG_SIZE_ONLY,FLAG_USE_SUFFIX)は必須項目から外し、下部で安全に取得します
    required_keys = [
        "BACKUP_SOURCE_DIR",
        "BACKUP_DESTINATION_DIR",
        "EXCLUDE_FILESIZE_MB",
        "EXCLUDE_FILE_EXTENSION",
        "FLAG_DEBUG_WAIT",
    ]
    for key in required_keys:
        if key not in raw_config:
            raise ValueError(
                f"不完全な設定データ: 必須キー '{key}' が存在しません。"
            )

    # --- 2. 文字列項目のサニタイズ（前後スペースの除去と型強制） ---
    src = str(raw_config["BACKUP_SOURCE_DIR"]).strip()
    dst = str(raw_config["BACKUP_DESTINATION_DIR"]).strip()
    ext = str(raw_config["EXCLUDE_FILE_EXTENSION"]).strip()

    # パスが空でないかチェック
    if not src or not dst:
        raise ValueError("コピー元（Src）またはコピー先（Dst）のパスが空です。")

    # 末尾スラッシュの強制適用（rsyncの安全な運用のための防衛策）
    if not src.endswith("/"):
        src += "/"
    if not dst.endswith("/"):
        dst += "/"

    # 実在するディレクトリかどうかの厳密なチェック
    # コマンドのスイッチ（例: -rf, --delete）や、不正な記号の混入をここで完全に遮断します
    if not os.path.isdir(src):
        raise ValueError(f"コピー元フォルダが存在しないか、不正なパスです: '{src}'")
    if not os.path.isdir(dst):
        raise ValueError(f"コピー先フォルダが存在しないか、不正なパスです: '{dst}'")

    sanitized["BACKUP_SOURCE_DIR"] = src
    sanitized["BACKUP_DESTINATION_DIR"] = dst

    # 拡張子の文字制限（半角英数字とカンマのみを許容。それ以外は除去して無毒化）
    # 悪意ある記号（*; $() など）をここで完全に削ぎ落とします
    ext_list = [e.strip() for e in ext.split(",")]
    clean_ext_list = []
    for e in ext_list:
        # 半角英数字のみで構成されている要素だけを抽出（空文字や不正記号は除外）
        if re.match(r"^[a-zA-Z0-9]+$", e):
            clean_ext_list.append(e)
    sanitized["EXCLUDE_FILE_EXTENSION"] = ",".join(clean_ext_list)

    # --- 3. 数値項目のサニタイズ（型変換と範囲チェック） ---
    try:
        size = int(raw_config["EXCLUDE_FILESIZE_MB"])
        if size < 1:
            # 0やマイナス値は強制的にデフォルト値（10MB）にするか、エラーにする
            # 今回は安全のため、最低値である 1 に補正（またはエラーでも可）
            size = 1
    except (ValueError, TypeError):
        # 数値に変換できない汚染データが入っていた場合は、安全のため例外にする
        raise ValueError(
            f"不正な値: EXCLUDE_FILESIZE_MB ('{raw_config['EXCLUDE_FILESIZE_MB']}') は整数である必要があります。"
        )
    sanitized["EXCLUDE_FILESIZE_MB"] = size

    # --- 4. ブーリアン項目のサニタイズ（型強制） ---
    # 文字列の "True" や "False"、数値の 1 や 0 が入ってきても厳密に bool 型に変換
    sanitized["FLAG_DEBUG_WAIT"] = bool(raw_config["FLAG_DEBUG_WAIT"])
    # 【新機能】JSONにキーが無ければデフォルト（False）を適用し、あれば厳密にbool化
    sanitized["FLAG_SIZE_ONLY"] = bool(raw_config.get("FLAG_SIZE_ONLY", False))
    sanitized["FLAG_USE_SUFFIX"] = bool(raw_config.get("FLAG_USE_SUFFIX", False))
    sanitized["FLAG_CHECKSUM"] = bool(raw_config.get("FLAG_CHECKSUM", False))

    return sanitized


def load_config_json() -> bool:
    """ホームディレクトリからJSON設定ファイルを読み込み、グローバル変数を更新する。

    エラーが発生した場合は、関数内でエラーダイアログを表示します。

    Returns:
        bool: JSONファイルが存在し、かつ読み込みに成功した場合は True。
              JSONファイルが存在しない場合、または読み込み・作成に失敗した場合は False。
    """
    global BACKUP_SOURCE_DIR, BACKUP_DESTINATION_DIR, EXCLUDE_FILESIZE_MB, EXCLUDE_FILE_EXTENSION, FLAG_DEBUG_WAIT
    global FLAG_SIZE_ONLY, FLAG_USE_SUFFIX, FLAG_CHECKSUM  # 【新機能 追加分】

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                raw_config_data = json.load(f)

            # 【重要】ここで生のデータをバリデーション＆サニタイズ（無毒化）する
            # 不正なデータがあれば、この内部で ValueError が発生して except 節へ飛びます
            config_data = validate_and_sanitize_config(raw_config_data)

            BACKUP_SOURCE_DIR = config_data.get("BACKUP_SOURCE_DIR", BACKUP_SOURCE_DIR)
            BACKUP_DESTINATION_DIR = config_data.get(
                "BACKUP_DESTINATION_DIR", BACKUP_DESTINATION_DIR
            )
            EXCLUDE_FILESIZE_MB = config_data.get("EXCLUDE_FILESIZE_MB", EXCLUDE_FILESIZE_MB)
            EXCLUDE_FILE_EXTENSION = config_data.get(
                "EXCLUDE_FILE_EXTENSION", EXCLUDE_FILE_EXTENSION
            )
            FLAG_DEBUG_WAIT = config_data.get("FLAG_DEBUG_WAIT", FLAG_DEBUG_WAIT)
            FLAG_SIZE_ONLY = config_data.get("FLAG_SIZE_ONLY", FLAG_SIZE_ONLY)
            FLAG_USE_SUFFIX = config_data.get("FLAG_USE_SUFFIX", FLAG_USE_SUFFIX)
            FLAG_CHECKSUM = config_data.get("FLAG_CHECKSUM", FLAG_CHECKSUM)

            print(f"[INFO] 設定をロードしました: {CONFIG_PATH}")
            return True

        except Exception as e:
            print(f"[ERROR] 設定ファイルの読み込みまたは検証に失敗しました: {e}")
            # 関数内でエラーダイアログを表示（文法エラーだけでなく、汚染データによるバリデーションエラーもキャッチ）
            _show_init_error_dialog(
                "初期化エラー",
                f"設定ファイル（JSON）の解析または安全性の検証に失敗しました。\n\n"
                f"パス: {CONFIG_PATH}\n"
                f"記述内容に不正な文字や値がないか確認してください。\n\n詳細: {e}",
            )
            return False

    else:
        # ファイルがない場合はデフォルト値で作成を試みる
        default_config = {
            "BACKUP_SOURCE_DIR": BACKUP_SOURCE_DIR,
            "BACKUP_DESTINATION_DIR": BACKUP_DESTINATION_DIR,
            "EXCLUDE_FILESIZE_MB": EXCLUDE_FILESIZE_MB,
            "EXCLUDE_FILE_EXTENSION": EXCLUDE_FILE_EXTENSION,
            "FLAG_DEBUG_WAIT": FLAG_DEBUG_WAIT,
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"[INFO] 初回のひな形ファイルを作成しました: {CONFIG_PATH}")

            # 初回作成時はエラーではないが、「ファイルを作ったので中身を確認・編集してね」
            # という意味を込めてユーザーに通知（不要であればこのダイアログは削除してもOKです）
            _show_init_error_dialog(
                "設定ファイル作成",
                f"初回の設定ファイル（ひな形）を作成しました。\n\n"
                f"パス: {CONFIG_PATH}\n"
                f"バックアップ元/先のパスを正しく書き換えてから、再度スクリプトを実行してください。",
                icon="info",
            )
        except Exception as e:
            print(f"[ERROR] 初回ファイルの作成に失敗しました: {e}")
            _show_init_error_dialog(
                "初期化エラー",
                f"設定ファイルが見つからず、新規作成にも失敗しました。\n\n"
                f"パス: {CONFIG_PATH}\n"
                f"フォルダの書き込み権限を確認してください。\n\n詳細: {e}",
            )

        return False


def _show_init_error_dialog(title: str, message: str, icon: str = "error") -> None:
    """Tkinter初期化前に安全にメッセージボックスを表示するためのヘルパー関数。

    Args:
        title (str): ダイアログボックスのタイトルバーに表示する文字列。
        message (str): ダイアログ内に表示する具体的なエラー内容や案内メッセージ。
        icon (str, optional): アイコンの種類（"error" または "info"）。デフォルトは "error"。
    """
    temp_root = tk.Tk()
    temp_root.withdraw()  # メインウィンドウを非表示にする
    if icon == "error":
        messagebox.showerror(title, message)
    else:
        messagebox.showinfo(title, message)
    temp_root.destroy()  # 使い終わったら確実に破棄


def confirm_execution_settings() -> bool:
    """ロードされたバックアップ設定をテキストにまとめ、標準ダイアログで実行確認を求める。

    Returns:
        bool: 「OK」が選択された場合は True、それ以外は False。
    """
    # テキストベースでシンプルに内容を構築
    msg = (
        "以下の条件でバックアップのスキャンを開始しますか？\n\n"
        f"■ コピー元Dir:\n   {BACKUP_SOURCE_DIR}\n\n"
        f"■ コピー先Dir:\n   {BACKUP_DESTINATION_DIR}\n\n"
        f"■ 除外サイズ: {EXCLUDE_FILESIZE_MB} MB 以上\n"
        f"■ 除外拡張子: {EXCLUDE_FILE_EXTENSION}\n"
        f"■ デバッグ用に表示を遅く: {'有効' if FLAG_DEBUG_WAIT else '無効'}"
    )

    # 一時的なルートウィンドウを作って非表示にする
    temp_root = tk.Tk()
    temp_root.withdraw()

    # 標準の「OK・キャンセル」ダイアログを表示
    # 返り値は OKなら True, キャンセルなら False
    result = messagebox.askokcancel("実行条件の確認", msg)

    temp_root.destroy()
    return result


class PreviewDialog(tk.Toplevel):
    """プレビューおよび実行ログを表示するためのカスタムサブウィンドウ。

    rsyncの実行前（ドライラン結果）や実行後（フルログ）を表示するために使用されます。
    テキストエリアの下に操作ボタンを配置し、スクロール可能な形式で情報を提示します。

    Attributes:
        result (bool): ユーザーが「バックアップ開始」を選択した場合は True、
            それ以外（キャンセルや閉じる）の場合は False。
        text_area (scrolledtext.ScrolledText): ログ内容を表示するスクロール可能なテキストウィジェット。
    """

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        log_content: str,
        show_start_button: bool = True
    ) -> None:
        """PreviewDialog クラスの初期化。

        Args:
            parent: 親となるコンポーネント（通常は主ウィンドウ）。
            title: ウィンドウのタイトルバーに表示する文字列。
            message: テキストエリアの上に表示する要約メッセージ。
            log_content: テキストエリアに表示する詳細なログ情報。
            show_start_button: 「バックアップ開始」ボタンを表示するかどうか。
                False の場合は「閉じる」ボタンのみが表示されます。
        """
        super().__init__(parent)
        self.title(title)
        self.geometry("750x550")
        self.minsize(600, 400)      # 最小サイズを制限
        self.result = False  # バックアップを開始するかどうか

        # --- 1. 上部：メッセージラベル ---
        tk.Label(
            self,
            text=message,
            justify="left",
            font=(
                "",
                10,
                "bold")).pack(
            pady=10,
            padx=10,
            anchor="w")

        # --- 2. 下部：ボタンエリア ---
        # side="bottom" で先に配置することで、テキストエリアが広がりすぎてもボタンが隠れないようにする
        btn_frame = tk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", pady=15)

        if show_start_button:
            # 実行ボタンを右側に配置
            tk.Button(btn_frame, text="バックアップ開始", width=18, height=1, bg="#4CAF50", fg="white",
                      font=("", 9, "bold"), command=self.on_start).pack(side="right", padx=20)
            tk.Button(
                btn_frame,
                text="キャンセル",
                width=12,
                height=1,
                command=self.destroy).pack(
                side="right",
                padx=10)
        else:
            tk.Button(
                btn_frame,
                text="閉じる",
                width=15,
                height=1,
                command=self.destroy).pack(
                side="bottom",
                pady=5)

        # --- 3. 中央：ログ表示用テキストエリア ---
        # heightの指定を小さくし、expand=Trueで広げるのがコツです
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.NONE, font=("Courier", 9))
        self.text_area.insert(tk.END, log_content)
        self.text_area.config(state=tk.DISABLED)
        self.text_area.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)

        # モーダルウィンドウとしての設定
        if parent:
            self.transient(parent)  # type: ignore
        self.grab_set()
        self.wait_window()

    def on_start(self) -> None:
        """「バックアップ開始」が押された際の処理。

        resultフラグをTrueに設定し、ダイアログを閉じます。
        """
        self.result = True
        self.destroy()


class BackupApp:
    """rsyncを使用したバックアップ進捗表示アプリケーション。

    Attributes:
        root (tk.Tk): tkinterのルートウィンドウ。
        process (Optional[subprocess.Popen]): 実行中のrsyncプロセス。
        is_running (bool): バックアップが実行中かどうかを管理するフラグ。
    """

    def __init__(self, root: tk.Tk) -> None:
        """アプリケーションの初期化とGUIコンポーネントの配置。

        Args:
            root (tk.Tk): tkinterのルートウィンドウ。
        """
        self.root: tk.Tk = root
        self.root.title("Rsync Backup Tool v2")
        self.root.geometry("550x220")

        # 1行目: ディレクトリ名表示用 (新規追加)
        self.label_dir: tk.Label = tk.Label(
            root, text="", anchor="w", justify="left", wraplength=500)
        self.label_dir.pack(fill="x", padx=20, pady=(10, 0))

        # 2行目: ファイル名・状態表示用 (既存の名前を維持)
        self.label: tk.Label = tk.Label(
            root,
            text="準備中...",
            anchor="w",
            justify="left",
            wraplength=500)
        self.label.pack(fill="x", padx=20, pady=(0, 10))

        self.progress: ttk.Progressbar = ttk.Progressbar(
            root, orient="horizontal", length=450, mode="determinate")
        self.progress.pack(pady=10)

        self.cancel_button: tk.Button = tk.Button(
            root, text="中断", command=self.stop_backup, state=tk.DISABLED)
        self.cancel_button.pack(pady=5)

        self.process: Optional[subprocess.Popen] = None
        self.is_running: bool = False
        self.full_log: str = ""  # 実行時の全ログを保持

        # 起動直後に事前チェックを開始
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self) -> None:
        """ディレクトリの存在確認を行い、問題なければスキャンを開始する。

        事前チェック（check_directories）が正常に通過した場合のみ、
        次のステップである事前ドライランスキャン（prepare_backup）を呼び出します。
        """
        if self.check_directories():
            self.prepare_backup()

    def check_directories(self) -> bool:
        """バックアップ元および先ディレクトリの妥当性をチェックする。

        Returns:
            bool: ディレクトリが有効な場合はTrue、無効な場合はFalse。
        """
        # ソースディレクトリの存在チェック
        if not os.path.exists(BACKUP_SOURCE_DIR):
            self.root.after(0, self.finish_backup, "エラー", f"バックアップ元が見つかりません:\n{BACKUP_SOURCE_DIR}")
            return False

        if not os.path.isdir(BACKUP_SOURCE_DIR):
            self.root.after(0, self.finish_backup, "エラー",
                            f"指定されたバックアップ元はディレクトリではありません:\n{BACKUP_SOURCE_DIR}")
            return False

        # バックアップ先ディレクトリの親ディレクトリ存在チェック
        # (バックアップ先自体はrsyncが作成可能だが、その親がないと失敗するため)
        dest_parent = os.path.dirname(BACKUP_DESTINATION_DIR.rstrip('/'))
        if dest_parent and not os.path.exists(dest_parent):
            self.root.after(0, self.finish_backup, "エラー", f"バックアップ先の親フォルダが存在しません:\n{dest_parent}")
            return False
        return True

    def prepare_backup(self) -> None:
        """rsyncのドライラン(-avhin)を実行して対象ファイル数を集計し、ユーザーに開始確認を求める。

        内部でrsyncプロセスを同期実行してログを解析し、転送対象ファイル数が0件の場合は
        メッセージを表示して即時終了します。1件以上ある場合は、コピペ用コマンドと
        日本語凡例を内包したプレビュー画面（PreviewDialog）をポップアップ表示します。

        Raises:
            subprocess.CalledProcessError: rsyncのドライランプロセスが異常終了した場合。
            Exception: パス解析やダイアログ生成などで予期せぬエラーが発生した場合。
        """
        self.label.config(text="バックアップ対象をスキャン中...")

        exclude_exts: List[str] = [ext.strip() for ext in EXCLUDE_FILE_EXTENSION.split(',')]
        exclude_args: List[str] = [f"--exclude=*.{ext}" for ext in exclude_exts]

        # 動的な追加スイッチの組み立て (FLAG_SIZE_ONLY, FLAG_USE_SUFFIX)
        extra_args: List[str] = []

        # 1. サイズ基準オプション
        if FLAG_SIZE_ONLY:
            extra_args.append("--size-only")

        # 2. 安全な退避オプション（現在時刻を展開して結合）
        if FLAG_USE_SUFFIX:
            # 実行時点の日付文字列（例: _bak20260624）を安全に生成
            import datetime
            suffix_resolved = datetime.datetime.now().strftime(BACKUP_SUFFIX_STR)
            extra_args.append("--backup")
            extra_args.append(f"--suffix={suffix_resolved}")

        # 3. 【新規】チェックサム比較オプション
        if FLAG_CHECKSUM:
            extra_args.append("--checksum")

        # 基本コマンドリストに動的引数をマージ
        # -i (--itemize-changes) を追加して、転送された項目を判別できるようにする
        cmd: List[str] = [
            "rsync", "-avhin",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
            *extra_args,
            BACKUP_SOURCE_DIR.rstrip('/') + '/',
            BACKUP_DESTINATION_DIR.rstrip('/') + '/'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.splitlines()
            target_files = sum(1 for line in lines if line.startswith(">f"))

            if target_files == 0:
                messagebox.showinfo("情報", "同期が必要なファイルはありません。")
                self.root.destroy()
                return

            confirm_msg = (
                f"バックアップ対象ファイル数: {target_files} 件\n"
                f"コピー元: {BACKUP_SOURCE_DIR}\n"
                f"コピー先: {BACKUP_DESTINATION_DIR}"
            )

            # --- 実行コマンドの文字列とitemize-changes凡例のテキストを生成し、仕切り線とともに出力結果の先頭に結合 ---
            cmd_str = " ".join(cmd)
            preview_content = _get_itemize_legend(cmd_str) + result.stdout

            # カスタムダイアログの表示（プレビュー機能）
            dialog = PreviewDialog(
                self.root,
                "バックアップの開始確認とプレビュー",
                confirm_msg,
                preview_content,  # 実行コマンド文字列 + 仕切り線 + ドライラン結果文字列
                show_start_button=True
            )

            if dialog.result:
                self.is_running = True
                self.cancel_button.config(state=tk.NORMAL)
                threading.Thread(target=self.run_rsync, args=(target_files,), daemon=True).start()
            else:
                self.root.destroy()

        except subprocess.CalledProcessError as e:
            self.root.after(0, self.finish_backup, "エラー", f"スキャンに失敗しました:\n{e.stderr}")
        except Exception as e:
            self.root.after(0, self.finish_backup, "エラー", f"予期せぬエラー: {str(e)}")

    def run_rsync(self, target_files: int) -> None:
        """rsyncコマンド(-avhi)を実行し、転送ファイル数に基づいて進捗率を計算・更新する。

        Args:
            target_files (int): バックアップ対象の総ファイル数。
        """

        exclude_exts: List[str] = [ext.strip() for ext in EXCLUDE_FILE_EXTENSION.split(',')]
        exclude_args: List[str] = [f"--exclude=*.{ext}" for ext in exclude_exts]

        # 動的な追加スイッチの組み立て (FLAG_SIZE_ONLY, FLAG_USE_SUFFIX)
        extra_args: List[str] = []

        # 1. サイズ基準オプション
        if FLAG_SIZE_ONLY:
            extra_args.append("--size-only")

        # 2. 安全な退避オプション（現在時刻を展開して結合）
        if FLAG_USE_SUFFIX:
            # 実行時点の日付文字列（例: _bak20260624）を安全に生成
            import datetime
            suffix_resolved = datetime.datetime.now().strftime(BACKUP_SUFFIX_STR)
            extra_args.append("--backup")
            extra_args.append(f"--suffix={suffix_resolved}")

        # 3. 【新規】チェックサム比較オプション
        if FLAG_CHECKSUM:
            extra_args.append("--checksum")

        # 基本コマンドリストに動的引数をマージ
        # -i (--itemize-changes) を追加して、転送された項目を判別できるようにする
        cmd: List[str] = [
            "rsync", "-avhi",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
            *extra_args,
            BACKUP_SOURCE_DIR.rstrip('/') + '/',
            BACKUP_DESTINATION_DIR.rstrip('/') + '/'
        ]

        completed_count: int = 0
        self.full_log = ""  # ログを初期化
        cmd_str = " ".join(cmd)  # 処理後のダイアログ表示で使うコマンド文字列

        try:
            os.makedirs(BACKUP_DESTINATION_DIR, exist_ok=True)
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )

            if self.process.stdout:
                for line in self.process.stdout:
                    if not self.is_running:
                        break

                    self.full_log += line  # 全ログを蓄積
                    if FLAG_DEBUG_WAIT:
                        time.sleep(0.5)  # デバッグ用に遅くする場合は0.5秒程度に大きくする
                    else:
                        time.sleep(0.01)  # 描画負荷軽減(0.01秒程度)

                    # -i オプションにより、ファイル転送時は行の先頭が ">f" などになる
                    # これをトリガーに「ファイル1つ完了」とみなす
                    # ※ディレクトリ作成 "cd"や 既存ディレクトリにコピー ".d" はカウントしない
                    if line.startswith('>f'):
                        completed_count += 1
                        if target_files > 0:
                            # 進捗率の計算 (かりに計算値が100を越えた場合、100以下に抑える)
                            percent = min(int((completed_count / target_files) * 100), 100)
                            # 進捗率のプログレスバー表示をアップデート
                            self.root.after(0, self.update_progress, percent)

                        # パスの解析
                        # ">f+++++++ path/to/file" からパス部分を抽出
                        parts = line.strip().split(' ', 1)
                        full_path = parts[1] if len(parts) > 1 else ""
                        dir_name, file_name = os.path.split(full_path)
                        # 処理中のディレクトリ名、ファイル名、進捗率の表示をアップデート
                        self.root.after(0, self.label_dir.config, {"text": f"フォルダ: {dir_name}"})
                        self.root.after(0, self.label.config, {
                            "text": f"コピー中 ({completed_count}/{target_files}): {file_name}"})

            self.process.wait()

            if self.is_running:
                # --- 実行コマンドの文字列とitemize-changes凡例のテキストを生成し、仕切り線とともに出力結果の先頭に結合 ---
                formatted_log = _get_itemize_legend(cmd_str) + self.full_log

                if self.process.returncode == 0:
                    self.root.after(0, self.update_progress, 100)
                    success_msg = f"正常に完了しました。\n(バックアップ対象ファイル数: {target_files} 件)"
                    self.root.after(0, self.show_final_log, "バックアップ完了", success_msg, formatted_log)
                else:
                    self.root.after(
                        0,
                        self.show_final_log,
                        "エラー",
                        f"rsyncエラーが発生しました。(Code: {self.process.returncode})",
                        formatted_log)

        except Exception as e:
            self.root.after(0, self.finish_backup, "エラー", f"致命的なエラー: {str(e)}")

    def update_progress(self, value: int) -> None:
        """プログレスバーの値を更新する。

        Args:
            value (int): セットする進捗率（0-100）。
        """

        self.progress['value'] = value

    def stop_backup(self) -> None:
        """バックアップ処理を中断し、アプリケーションを終了する。

        ユーザーに確認ダイアログを表示し、「はい」が選択された場合は
        実行中のrsyncサブプロセスを強制終了（terminate）した上で、GUIウィンドウを破棄します。
        """

        if messagebox.askyesno("中断確認", "バックアップを中断して終了しますか？"):
            self.is_running = False
            if self.process:
                self.process.terminate()
            self.root.destroy()

    def show_final_log(self, title: str, message: str, formatted_log: str) -> None:
        """完了後にログを閲覧できるウィンドウを表示する。

        バックアップ処理終了後に、結果概要メッセージとともに、実際に実行したコマンド、
        および日本語凡例が先頭に付与された成形済みのログを閲覧用ダイアログに渡して表示します。

        Args:
            title (str): ログ閲覧ダイアログのタイトル（「バックアップ完了」や「エラー」など）。
            message (str): ダイアログ上部に表示する、処理結果のサマリーメッセージ。
            formatted_log (str): コマンド・凡例ヘッダーと、rsyncの標準出力が結合された全ログ文字列。
        """

        PreviewDialog(self.root, title, message, formatted_log, show_start_button=False)
        self.root.destroy()

    def finish_backup(self, title: str, message: str) -> None:
        """エラーや例外の発生時に、ユーザーへメッセージを表示してアプリケーションを安全に終了する。

        Args:
            title (str): メッセージボックスのタイトル。
            message (str): メッセージボックスに表示するエラーや異常終了の具体的な詳細内容。
        """

        messagebox.showinfo(title, message)
        self.root.destroy()


if __name__ == "__main__":
    # 1. 設定ファイルの読み込みを試行 (エラー時は関数内でダイアログが出ます)
    if load_config_json():
        # 2. 成功（True）の場合、バックアップ条件を表示してユーザ確認を求める
        if confirm_execution_settings():

            # 3. メインGUIの処理に進む
            root: tk.Tk = tk.Tk()
            app: BackupApp = BackupApp(root)
            root.mainloop()
        else:
            print("[INFO] ユーザーによってキャンセルされました。")
            sys.exit(0)
    else:
        # False の場合は静かに終了する（すでにダイアログでユーザー通知済みのため）
        print("[INFO] アプリケーションを終了します。")
        sys.exit(0)
