#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定ディレクトリを常時監視し、画像検出時にExif復元・DB登録処理を全自動実行するGUIメインスクリプト。

このモジュールは、watchdog ライブラリを使用してユーザーがGUIで指定したディレクトリを監視し、
対象画像（.jpg, .jpeg）のイベントを検知した際に動的にロードした外部スクリプト（05_exif_restore_from_gimp.py）の
自動処理関数を呼び出してExif復元またはDB登録を実行します。
また、ユーザーがダイアログで指定したディレクトリ内の全既存画像ファイルに対する一括処理機能および簡易表示切替を提供します。

Attributes:
    RESTORE_SCRIPT_NAME (str): 呼び出すExif復元スクリプト名（デフォルト: 05_exif_restore_from_gimp.py）。
    JSON_DATABASE_DIRECTORY_PATH (str): JSON データベースの保存先ディレクトリ（デフォルト: ~/）。
    JSON_DATABASE_FILE_NAME (str): データベースのファイル名（デフォルト: .exif_restore_from_gimp.json）。
    JSON_DATABASE_FULL_PATH (str): データベースファイルのフルパス。
    DEFAULT_WATCH_DIRECTORY_PATH (str): 監視対象とするデフォルトディレクトリのパス（デフォルト: ~/Desktop）。
    TARGET_FILE_EXTENSIONS (Set[str]): 監視対象とするファイル拡張子の集合（例: {".jpg", ".jpeg"}）。
    DEBOUNCE_INTERVAL_SECONDS (float): 同一ファイルに対する重複イベント発火を無視する間隔（秒）。

Requires:
    - Python 3.x
    - watchdog: ファイルシステムイベント監視用ライブラリ (pip install watchdog)
    - 05_exif_restore_from_gimp.py: 同一ディレクトリ内に配置されている必要のあるExif復元処理スクリプト

Author:
    Google Gemini Collaborative Coding

Version:
    1.0.0 (2026/08/19) (06_main_watch_and_restore.py としてテキスト版 最初の実装)
    2.0.0 (2026/08/21) tkinter GUI化
    2.1.0 (2026/08/22) 指定ディレクトリ内全ファイルの一括自動処理ボタン機能を追加
    2.2.0 (2026/08/22) 一括処理時のフォルダ選択ダイアログ追加および自動監視停止・再開制御の実装
    2.3.0 (2026/08/23) 簡易表示（1対象1行表示）のチェックボックス機能を追加
"""

import importlib.util
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from typing import Any, Dict, Optional, Set

from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
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

# 監視対象のデフォルトディレクトリパス
DEFAULT_WATCH_DIRECTORY_PATH: str = os.path.expanduser("~/Desktop")

# 監視対象のファイル拡張子（小文字で指定）
TARGET_FILE_EXTENSIONS: Set[str] = {".jpg", ".jpeg"}

# 同一ファイルに対するイベント発火をまとめる判定時間（秒）
DEBOUNCE_INTERVAL_SECONDS: float = 1.0


def load_exif_restore_module(script_name: str) -> Any:
    """指定されたファイル名（スクリプトと同階層）から Python モジュールを動的にインポートします。

    Args:
        script_name (str): 読み込む Python スクリプトのファイル名

    Returns:
        Any: インポートされたモジュールオブジェクト（失敗時は None）
    """
    # ── [ステップ1] 実行中スクリプトと同階層のフルパスを構築 ──
    current_directory = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_directory, script_name)

    if not os.path.exists(script_path):
        print(f"エラー: 書き換えスクリプトが見つかりません -> {script_path}")
        return None

    # ── [ステップ2] モジュールの動的読み込み処理 ──
    try:
        module_name = "exif_restore_module"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            print(f"エラー: モジュールのロードに失敗しました -> {script_path}")
            return None

        loaded_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded_module)
        return loaded_module
    except Exception as error_exception:
        print(
            f"エラー: モジュールのインポート中に例外が発生しました -> {error_exception}"
        )
        return None


class TextRedirector:
    """標準出力を tkinter の Text ウィジェットへリダイレクトするクラス。"""

    def __init__(self, text_widget: scrolledtext.ScrolledText) -> None:
        """TextRedirector クラスの初期化処理を行います。

        Args:
            text_widget (scrolledtext.ScrolledText): 出力先となるテキストウィジェット
        """
        self.text_widget: scrolledtext.ScrolledText = text_widget

    def write(self, str_data: str) -> None:
        """文字列をテキストウィジェットに挿入し、最新行へ自動スクロールします。

        Args:
            str_data (str): 挿入するテキストデータ
        """
        self.text_widget.insert(tk.END, str_data)
        self.text_widget.see(tk.END)

    def flush(self) -> None:
        """標準出力インターフェースとの互換性のための空メソッド。"""
        pass


class ImageFileEventHandler(FileSystemEventHandler):
    """指定されたディレクトリ内でファイルの作成・移動・更新イベントを監視し、

    外部モジュールを呼び出して自動処理を実行するハンドラクラス。
    """

    def __init__(
        self,
        watch_extensions: Set[str],
        debounce_interval: float = 1.0,
        is_simple_mode_variable: Optional[tk.BooleanVar] = None,
    ) -> None:
        """イベントハンドラの初期化処理を行います。

        Args:
            watch_extensions (Set[str]): 監視対象とする拡張子の集合
            debounce_interval (float): 重複検知を無視する秒数間隔
            is_simple_mode_variable (Optional[tk.BooleanVar]): 簡易表示設定の BooleanVar オブジェクト
        """
        super().__init__()
        self.watch_extensions: Set[str] = {
            extension.lower() for extension in watch_extensions
        }
        self.debounce_interval: float = debounce_interval
        self.is_simple_mode_variable: Optional[tk.BooleanVar] = is_simple_mode_variable

        # ファイルパスごとの「最終イベント発生時刻」を記録する辞書
        self.last_event_timestamps: Dict[str, float] = {}

        # ── [ステップ1] Exif書き戻しモジュールの読み込みと検証 ──
        self.restore_module = load_exif_restore_module(RESTORE_SCRIPT_NAME)

        if self.restore_module is None:
            print(f"エラー: {RESTORE_SCRIPT_NAME} の読み込みに失敗しました。")
            return

        # モジュール内に自動処理用の主関数が存在するか確認
        if not hasattr(self.restore_module, "process_image_file_automatically"):
            print(
                f"エラー: {RESTORE_SCRIPT_NAME} 内に 'process_image_file_automatically' 関数が見つかりません。"
            )
            self.restore_module = None

    def _is_target_file(self, file_path: str) -> bool:
        """対象ファイルが監視対象の拡張子を持つか判定します。

        Args:
            file_path (str): チェック対象のファイルパス

        Returns:
            bool: 監視対象であれば True
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in self.watch_extensions

    def _should_process_event(self, file_path: str) -> bool:
        """デバウンス判定を行い、処理を実行すべきイベントか判定します。

        Args:
            file_path (str): イベントが発生したファイルのパス

        Returns:
            bool: 処理を実行すべきイベントであれば True
        """
        current_time = time.time()
        last_time = self.last_event_timestamps.get(file_path, 0.0)

        if (current_time - last_time) < self.debounce_interval:
            self.last_event_timestamps[file_path] = current_time
            return False

        self.last_event_timestamps[file_path] = current_time
        return True

    def _handle_file_event(self, event_type: str, file_path: str) -> None:
        """イベントの共通検証および Exif 情報の書き戻し/DB自動登録処理を行います。

        Args:
            event_type (str): イベント種別を表す文字列
            file_path (str): 対象ファイルのパス
        """
        absolute_path = os.path.abspath(file_path)

        # ── [ステップ2] 拡張子チェックとデバウンス判定および自動処理の実行 ──
        if self._is_target_file(absolute_path):
            if self._should_process_event(absolute_path):
                is_simple = (
                    self.is_simple_mode_variable.get()
                    if self.is_simple_mode_variable
                    else False
                )

                if not is_simple:
                    print(f"[{event_type}]: {absolute_path}")

                if self.restore_module is None:
                    print(
                        "エラー: 復元モジュールが正しくロードされていないため、処理をスキップします。"
                    )
                    return

                try:
                    # GIMPからの保存完了直後のファイルロックを防ぐため待機
                    time.sleep(0.5)

                    # 05_exif_restore_from_gimp.py の自動判定・処理関数を呼び出す
                    is_success = self.restore_module.process_image_file_automatically(
                        absolute_path, JSON_DATABASE_FULL_PATH, is_simple
                    )
                    if not is_simple:
                        if is_success:
                            print(
                                f"  └─ [正常完了] 画像の処理に成功しました: {absolute_path}"
                            )
                        else:
                            print(
                                f"  └─ [警告] 画像の処理が中断またはスキップされました: {absolute_path}"
                            )

                except Exception as error_exception:
                    print(
                        f"  └─ [エラー] 画像処理中に例外が発生しました: {error_exception}"
                    )

    def on_created(self, event: FileCreatedEvent) -> None:
        """ファイル新規作成時のイベントハンドラ。"""
        if not event.is_directory:
            self._handle_file_event("新規ファイル検知 (Created)", event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """ファイル移動／名前変更時のイベントハンドラ。"""
        if not event.is_directory:
            self._handle_file_event("ファイル保存検知 (Moved/Renamed)", event.dest_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        """ファイル更新時のイベントハンドラ。"""
        if not event.is_directory:
            self._handle_file_event("ファイル更新検知 (Modified)", event.src_path)


class MainWatchAndRestoreApp(tk.Tk):
    """ディレクトリ監視および Exif 自動復元を行う tkinter GUI アプリケーションクラス。"""

    def __init__(self) -> None:
        """GUI アプリケーションの構築と初期設定を行います。"""
        super().__init__()

        # ── [ステップ1] ウィンドウ基本設定 ──
        self.title("GIMP Exif 自動復元・ディレクトリ監視ツール (GUI版)")
        self.geometry("820x580")

        self.observer_instance: Optional[Observer] = None
        self.is_monitoring: bool = False
        self.is_batch_processing: bool = False

        # 簡易表示フラグ用 BooleanVar
        self.is_simple_mode_variable = tk.BooleanVar(value=False)

        # ── [ステップ2] UI レイアウトの生成 ──
        directory_frame = ttk.Frame(self)
        directory_frame.pack(fill=tk.X, padx=10, pady=10)

        self.directory_path_variable = tk.StringVar(value=DEFAULT_WATCH_DIRECTORY_PATH)

        directory_label = ttk.Label(directory_frame, text="監視ディレクトリ:")
        directory_label.pack(side=tk.LEFT, padx=(0, 5))

        directory_entry = ttk.Entry(
            directory_frame, textvariable=self.directory_path_variable
        )
        directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        select_button = ttk.Button(
            directory_frame,
            text="参照...",
            command=self.select_directory_path,
        )
        select_button.pack(side=tk.RIGHT)

        # 操作用ボタンの配置
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.start_button = ttk.Button(
            button_frame, text="監視開始", command=self.start_monitoring
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(
            button_frame,
            text="監視停止",
            command=self.stop_monitoring,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))

        # 一括処理用のボタン
        self.batch_process_button = ttk.Button(
            button_frame,
            text="指定ディレクトリ内の全ファイルを処理",
            command=self.execute_batch_processing,
        )
        self.batch_process_button.pack(side=tk.LEFT, padx=(0, 15))

        # 簡易表示チェックボックスの配置
        simple_mode_checkbutton = ttk.Checkbutton(
            button_frame,
            text="簡易表示",
            variable=self.is_simple_mode_variable,
        )
        simple_mode_checkbutton.pack(side=tk.LEFT)

        # ログ表示用 ScrolledText ウィジェット
        self.log_text_widget = scrolledtext.ScrolledText(
            self, state="normal", wrap=tk.WORD
        )
        self.log_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # ── [ステップ3] 標準出力のリダイレクトおよび終了処理の設定 ──
        sys.stdout = TextRedirector(self.log_text_widget)
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

    def select_directory_path(self) -> None:
        """フォルダ選択ダイアログを表示し、選択結果をテキストボックスに反映します。"""
        selected_path = filedialog.askdirectory(
            initialdir=self.directory_path_variable.get()
        )
        if selected_path:
            self.directory_path_variable.set(selected_path)

    def start_monitoring(self) -> None:
        """監視スレッドを立ち上げ、ファイル監視およびExif復元処理を開始します。"""
        target_directory_path = os.path.abspath(self.directory_path_variable.get())

        if not os.path.exists(target_directory_path):
            print(
                f"[エラー]: 選択されたディレクトリが存在しません -> {target_directory_path}"
            )
            return

        # ── [ステップ1] UI状態の更新 ──
        self.is_monitoring = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        # ── [ステップ2] Observer スレッドの開始 ──
        event_handler = ImageFileEventHandler(
            watch_extensions=TARGET_FILE_EXTENSIONS,
            debounce_interval=DEBOUNCE_INTERVAL_SECONDS,
            is_simple_mode_variable=self.is_simple_mode_variable,
        )
        self.observer_instance = Observer()
        self.observer_instance.schedule(
            event_handler, path=target_directory_path, recursive=False
        )
        self.observer_instance.start()

        print("=" * 70)
        print("ディレクトリの監視およびExif復元タスクを開始しました...")
        print(f"  ・対象ディレクトリ  : {target_directory_path}")
        print(f"  ・対象拡張子        : {', '.join(TARGET_FILE_EXTENSIONS)}")
        print(f"  ・読み込みスクリプト : {RESTORE_SCRIPT_NAME}")
        print(f"  ・データベースパス  : {JSON_DATABASE_FULL_PATH}")
        print("=" * 70)

    def stop_monitoring(self) -> None:
        """ファイル監視を安全に停止します。"""
        if self.observer_instance and self.is_monitoring:
            self.observer_instance.stop()
            self.observer_instance.join()
            self.observer_instance = None
            self.is_monitoring = False

            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

            print("監視を停止しました。")

    def execute_batch_processing(self) -> None:
        """一括処理用ディレクトリを選択させ、監視一時停止およびバックグラウンド一括処理を開始します。"""
        if self.is_batch_processing:
            print("[警告]: 現在一括処理が既に実行中です。完了までお待ちください。")
            return

        # ── [ステップ1] ダイアログによる一括処理対象フォルダの選択 ──
        selected_batch_directory = filedialog.askdirectory(
            title="一括処理を行うディレクトリを選択してください",
            initialdir=self.directory_path_variable.get(),
        )

        if not selected_batch_directory:
            print("一括処理がキャンセルされました。")
            return

        target_directory_path = os.path.abspath(selected_batch_directory)
        if not os.path.exists(target_directory_path):
            print(
                f"[エラー]: 選択されたディレクトリが存在しません -> {target_directory_path}"
            )
            return

        # ── [ステップ2] 監視状態の確認と一時停止 ──
        was_monitoring_active = self.is_monitoring
        if was_monitoring_active:
            print("\n一括処理実行に伴い、ディレクトリの自動監視を一時停止します...")
            self.stop_monitoring()

        # ── [ステップ3] 別スレッドで一括処理を実行 ──
        worker_thread = threading.Thread(
            target=self._process_all_files_in_directory,
            args=(target_directory_path, was_monitoring_active),
            daemon=True,
        )
        worker_thread.start()

    def _process_all_files_in_directory(
        self, target_directory_path: str, should_resume_monitoring: bool
    ) -> None:
        """指定ディレクトリ内の全jpg/jpegファイルを探索し順次処理を行う内部メソッド（別スレッド実行用）。

        Args:
            target_directory_path (str): 処理対象のディレクトリパス
            should_resume_monitoring (bool): 一括処理完了後に自動監視を再開するかどうか
        """
        self.is_batch_processing = True
        self.batch_process_button.config(state=tk.DISABLED)

        try:
            print("=" * 70)
            print("一括処理タスクを開始します...")
            print(f"  ・対象ディレクトリ  : {target_directory_path}")

            # ── [ステップ1] 外部モジュールの動的読み込み ──
            restore_module = load_exif_restore_module(RESTORE_SCRIPT_NAME)

            if restore_module is None or not hasattr(
                restore_module, "process_image_file_automatically"
            ):
                print(
                    f"[エラー]: {RESTORE_SCRIPT_NAME} の読み込み、または process_image_file_automatically 関数の呼び出しに失敗しました。"
                )
                return

            # ── [ステップ2] 対象ファイルリストの抽出 ──
            target_file_list = []
            for file_name in os.listdir(target_directory_path):
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension in TARGET_FILE_EXTENSIONS:
                    target_file_list.append(
                        os.path.join(target_directory_path, file_name)
                    )

            target_file_list.sort()
            total_file_count = len(target_file_list)

            print(f"  ・対象ファイル数    : {total_file_count} 件")
            print("=" * 70)

            if total_file_count == 0:
                print("処理対象の画像ファイル (.jpg, .jpeg) が見つかりませんでした。")
                return

            # ── [ステップ3] 各ファイルに対して順次処理を実行 ──
            success_count = 0
            is_simple = self.is_simple_mode_variable.get()

            for index, file_path in enumerate(target_file_list, start=1):
                if not is_simple:
                    print(f"[{index}/{total_file_count}] 処理中: {file_path}")
                try:
                    is_success = restore_module.process_image_file_automatically(
                        file_path, JSON_DATABASE_FULL_PATH, is_simple
                    )
                    if is_success:
                        if not is_simple:
                            print(f"  └─ [正常完了] 処理成功: {file_path}")
                        success_count += 1
                    else:
                        if not is_simple:
                            print(f"  └─ [警告] スキップまたは失敗: {file_path}")
                except Exception as error_exception:
                    print(f"  └─ [エラー] 例外が発生しました: {error_exception}")

            print("-" * 70)
            print(
                f"一括処理が完了しました (成功: {success_count} / 全 {total_file_count} 件)"
            )
            print("-" * 70)

        finally:
            self.is_batch_processing = False
            self.batch_process_button.config(state=tk.NORMAL)

            # ── [ステップ4] 以前監視状態だった場合は自動で監視を再開 ──
            if should_resume_monitoring:
                print("\n一時停止していた自動監視を再開します...")
                self.start_monitoring()

    def on_close_window(self) -> None:
        """アプリ終了時に監視スレッドを停止させてからウィンドウを閉じます。"""
        if self.is_monitoring:
            self.stop_monitoring()
        self.destroy()


def main() -> None:
    """メイン処理を実行し、GUI画面を起動します。"""
    app = MainWatchAndRestoreApp()
    app.mainloop()


if __name__ == "__main__":
    main()
