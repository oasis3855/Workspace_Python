#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定ディレクトリを常時監視し、画像検出時にExif復元・DB登録処理を全自動実行するメインスクリプト。

このモジュールは、watchdog ライブラリを使用して特定のディレクトリ（デフォルト: デスクトップ）を監視し、
対象の画像ファイル（.jpg, .jpeg）の新規作成・移動・更新イベントを検知します。
イベント発生時はデバウンス処理（重複検知抑止）およびファイル書き込み完了待ち（0.5秒）を行った後、
動的にロードした `05_exif_restore_from_gimp.py` の自動処理関数を呼び出して、
オリジナル画像の「DB自動登録」または Gimp 編集画像の「Exif自動復元」をバックグラウンドでシームレスに実行します。

Attributes:
    RESTORE_SCRIPT_NAME (str): 呼び出すExif復元スクリプト名（デフォルト: 05_exif_restore_from_gimp.py）。
    JSON_DATABASE_DIRECTORY_PATH (str): JSON データベースの保存先ディレクトリ（デフォルト: ~/）。
    JSON_DATABASE_FILE_NAME (str): データベースのファイル名（デフォルト: .exif_restore_from_gimp.json）。
    JSON_DATABASE_FULL_PATH (str): データベースファイルのフルパス。
    WATCH_DIRECTORY_PATH (str): 監視対象とするディレクトリのパス（デフォルト: ~/Desktop）。
    TARGET_FILE_EXTENSIONS (Set[str]): 監視対象とするファイル拡張子の集合（例: {".jpg", ".jpeg"}）。
    DEBOUNCE_INTERVAL_SECONDS (float): 同一ファイルに対する重複イベント発火を無視する間隔（秒）。

Requires:
    - Python 3.x
    - watchdog: ファイルシステムイベント監視用ライブラリ (pip install watchdog)
    - Pillow (PIL): 画像処理・Exifデータ解析用ライブラリ (pip install Pillow)
    - 05_exif_restore_from_gimp.py: 同一ディレクトリ内に配置されている必要のあるExif復元処理スクリプト

Author:
    Google Gemini3.6 Flash Collaborating Coding

Version:
    1.0.0 (2026/08/19)
"""

import importlib.util
import os
import sys
import time
from typing import Any, Dict, Set

from watchdog.events import FileCreatedEvent, FileSystemEventHandler, FileModifiedEvent, FileMovedEvent
from watchdog.observers import Observer

# ── [グローバル変数（設定項目）] ──
# 呼び出すExif復元スクリプトのファイル名
RESTORE_SCRIPT_NAME: str = "05_exif_restore_from_gimp.py"

# データベース JSON ファイルの出力先ディレクトリおよびファイル名
JSON_DATABASE_DIRECTORY_PATH: str = os.path.expanduser("~/")
JSON_DATABASE_FILE_NAME: str = ".exif_restore_from_gimp.json"

# JSON ファイルのフルパス構築
JSON_DATABASE_FULL_PATH: str = os.path.join(
    JSON_DATABASE_DIRECTORY_PATH, JSON_DATABASE_FILE_NAME
)

# 監視対象のディレクトリパス
WATCH_DIRECTORY_PATH: str = os.path.expanduser("~/Desktop")

# 監視対象のファイル拡張子（小文字で指定）
TARGET_FILE_EXTENSIONS: Set[str] = {".jpg", ".jpeg"}

# 同一ファイルに対するイベント発火をまとめる判定時間（秒）
DEBOUNCE_INTERVAL_SECONDS: float = 1.0


def load_exif_restore_module(script_name: str) -> Any:
    """
    指定されたファイル名（スクリプトと同階層）から Python モジュールを動的にインポートする。

    Args:
        script_name (str): 読み込む Python スクリプトのファイル名

    Returns:
        Any: インポートされたモジュールオブジェクト
    """
    # ── [ステップ1] 実行中スクリプトと同階層のフルパスを構築 ──
    current_directory = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_directory, script_name)

    if not os.path.exists(script_path):
        print(f"エラー: 書き換えスクリプトが見つかりません -> {script_path}", file=sys.stderr)
        sys.exit(1)

    # ── [ステップ2] モジュールの動的読み込み処理 ──
    module_name = "exif_restore_module"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"モジュールのロードに失敗しました: {script_path}")

    loaded_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded_module)
    return loaded_module


class ImageFileEventHandler(FileSystemEventHandler):
    """
    指定されたディレクトリ内でファイルの作成・移動・更新イベントを監視し、
    連続する重複イベントをデバウンス（間引き）して検知するハンドラクラス。
    """

    def __init__(
        self, watch_extensions: Set[str], debounce_interval: float = 1.0
    ) -> None:
        """
        イベントハンドラの初期化処理を行います。

        Args:
            watch_extensions (Set[str]): 監視対象とする拡張子の集合
            debounce_interval (float): 重複検知を無視する秒数間隔
        """
        super().__init__()
        self.watch_extensions: Set[str] = {
            extension.lower() for extension in watch_extensions
        }
        self.debounce_interval: float = debounce_interval

        # ファイルパスごとの「最終イベント発生時刻」を記録する辞書
        self.last_event_timestamps: Dict[str, float] = {}

        # ── [ステップ3] Exif書き戻しモジュールの読み込みと検証 ──
        self.restore_module = load_exif_restore_module(RESTORE_SCRIPT_NAME)

        # モジュール内に自動処理用の主関数が存在するか確認
        if not hasattr(self.restore_module, "process_image_file_automatically"):
            print(
                f"エラー: {RESTORE_SCRIPT_NAME} 内に 'process_image_file_automatically' 関数が見つかりません。",
                file=sys.stderr,
            )
            sys.exit(1)

    def _is_target_file(self, file_path: str) -> bool:
        """
        対象ファイルが監視対象の拡張子を持つか判定します。

        Args:
            file_path (str): チェック対象のファイルパス

        Returns:
            bool: 監視対象であれば True
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in self.watch_extensions

    def _should_process_event(self, file_path: str) -> bool:
        """
        デバウンス判定を行い、処理を実行すべきイベントか判定します。
        指定間隔以内に発生した連続イベントは無視します。

        Args:
            file_path (str): イベントが発生したファイルのパス

        Returns:
            bool: 処理を実行すべきイベントであれば True
        """
        current_time = time.time()
        last_time = self.last_event_timestamps.get(file_path, 0.0)

        # 最後に検知した時刻からの経過時間を計算
        if (current_time - last_time) < self.debounce_interval:
            # 短時間での連続イベントのため無視する（タイムスタンプのみ更新）
            self.last_event_timestamps[file_path] = current_time
            return False

        # 規定時間を過ぎているため処理を実行対象とする
        self.last_event_timestamps[file_path] = current_time
        return True

    def _handle_file_event(self, event_type: str, file_path: str) -> None:
        """
        イベントの共通検証および Exif 情報の書き戻し/DB自動登録処理を行います。

        Args:
            event_type (str): イベント種別を表す文字列
            file_path (str): 対象ファイルのパス
        """
        absolute_path = os.path.abspath(file_path)

        # ── [ステップ4] 拡張子チェックとデバウンス判定および自動処理の実行 ──
        if self._is_target_file(absolute_path):
            if self._should_process_event(absolute_path):
                print(f"[{event_type}]: {absolute_path}")
                try:
                    # GIMPからの保存完了直後のファイルロックを防ぐため待機
                    time.sleep(0.5)

                    # 05_exif_restore_from_gimp.py の自動判定・処理関数を呼び出す
                    is_success = self.restore_module.process_image_file_automatically(
                        absolute_path, JSON_DATABASE_FULL_PATH
                    )
                    if is_success:
                        print(f"  └─ [正常完了] 画像の処理に成功しました: {absolute_path}")
                    else:
                        print(f"  └─ [警告] 画像の処理が中断またはスキップされました: {absolute_path}")

                except Exception as error_exception:
                    print(f"  └─ [エラー] 画像処理中に例外が発生しました: {error_exception}", file=sys.stderr)

    def on_created(self, event: FileCreatedEvent) -> None:
        """
        ファイル新規作成時のイベントハンドラ。
        """
        if not event.is_directory:
            self._handle_file_event("新規ファイル検知 (Created)", event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """
        ファイル移動／名前変更時のイベントハンドラ。
        """
        if not event.is_directory:
            self._handle_file_event(
                "ファイル保存検知 (Moved/Renamed)", event.dest_path
            )

    def on_modified(self, event: FileModifiedEvent) -> None:
        """
        ファイル更新時のイベントハンドラ。
        """
        if not event.is_directory:
            self._handle_file_event("ファイル更新検知 (Modified)", event.src_path)


def start_directory_monitoring(
    directory_path: str,
    target_extensions: Set[str],
    debounce_interval: float,
) -> None:
    """
    指定されたディレクトリの監視を開始します。

    Args:
        directory_path (str): 監視対象ディレクトリのパス
        target_extensions (Set[str]): 監視対象のファイル拡張子の集合
        debounce_interval (float): 重複イベントの間引き時間（秒）

    Returns:
        None
    """
    absolute_directory_path = os.path.abspath(directory_path)

    if not os.path.exists(absolute_directory_path):
        print(f"エラー: 監視対象のディレクトリが存在しません -> {absolute_directory_path}")
        sys.exit(1)

    event_handler = ImageFileEventHandler(
        watch_extensions=target_extensions, debounce_interval=debounce_interval
    )
    observer = Observer()

    observer.schedule(
        event_handler, path=absolute_directory_path, recursive=False
    )

    observer.start()
    print("=" * 70)
    print(f"ディレクトリの監視を開始しました...")
    print(f"  ・対象ディレクトリ  : {absolute_directory_path}")
    print(f"  ・対象拡張子        : {', '.join(target_extensions)}")
    print(f"  ・デバウンス間隔    : {debounce_interval} 秒")
    print(f"  ・読み込みスクリプト : {RESTORE_SCRIPT_NAME}")
    print(f"  ・データベースパス  : {JSON_DATABASE_FULL_PATH}")
    print("  ※ 終了するには Ctrl+C を押してください。")
    print("=" * 70)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n監視停止のリクエストを受け取りました。安全に停止処理を行っています...")
    finally:
        observer.stop()
        observer.join()
        print("監視を停止しました。")


if __name__ == "__main__":
    # ── [ステップ5] 監視用グローバル変数を使用した監視処理の起動 ──
    # 監視対象ディレクトリが存在しない場合は自動生成する
    if not os.path.exists(WATCH_DIRECTORY_PATH):
        os.makedirs(WATCH_DIRECTORY_PATH, exist_ok=True)

    # 定義済みのグローバル設定値を用いてディレクトリ監視を開始
    start_directory_monitoring(
        directory_path=WATCH_DIRECTORY_PATH,
        target_extensions=TARGET_FILE_EXTENSIONS,
        debounce_interval=DEBOUNCE_INTERVAL_SECONDS,
    )
