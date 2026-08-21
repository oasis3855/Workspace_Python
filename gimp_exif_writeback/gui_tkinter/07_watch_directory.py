#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定ディレクトリ内の画像ファイル操作をリアルタイムで監視・検知するGUIスクリプト。

このモジュールは、watchdog ライブラリを使用してユーザーが選択したディレクトリを
常時監視し、対象の拡張子（.jpg, .jpeg）を持つファイルの新規作成・移動・更新イベントをリアルタイムに検知します。
監視処理はバックグラウンドスレッドで動作し、ログメッセージを tkinter の ScrolledText に表示します。

Requires:
    - Python 3.x
    - watchdog: ファイルシステムイベント監視用ライブラリ (pip install watchdog)

Author:
    Google Gemini3.6 Flash Collaborating Coding

Version:
    1.0.0 (2026/08/15) (04_watch_directory.pyとして テキスト版 最初の実装)
    2.0.0 (2026/08/21) tkinter GUI化
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from typing import Dict, Set, Optional
from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

# ── [グローバル変数（設定項目）] ──
# デフォルトの監視対象ディレクトリパス
DEFAULT_WATCH_DIRECTORY_PATH: str = os.path.expanduser("~/Desktop")

# 監視対象のファイル拡張子（小文字で指定）
TARGET_FILE_EXTENSIONS: Set[str] = {".jpg", ".jpeg"}

# 同一ファイルに対するイベント発火をまとめる判定時間（秒）
DEBOUNCE_INTERVAL_SECONDS: float = 1.0


class TextRedirector:
    """標準出力を tkinter の Text ウィジェットへリダイレクトするクラス。"""

    def __init__(self, text_widget: scrolledtext.ScrolledText) -> None:
        """TextRedirector クラスの初期化処理を行ないます。

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

    連続する重複イベントをデバウンス（間引き）して検知するハンドラクラス。
    """

    def __init__(
        self, watch_extensions: Set[str], debounce_interval: float = 1.0
    ) -> None:
        """イベントハンドラの初期化処理を行います。

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
        """イベントの共通検証とログ出力処理を行います。

        Args:
            event_type (str): イベント種別を表す文字列
            file_path (str): 対象ファイルのパス
        """
        absolute_path = os.path.abspath(file_path)

        # ── [ステップ1] 拡張子チェックとデバウンス判定 ──
        if self._is_target_file(absolute_path):
            if self._should_process_event(absolute_path):
                print(f"[{event_type}]: {absolute_path}")

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


class DirectoryWatcherApp(tk.Tk):
    """ディレクトリ監視を行う tkinter GUI アプリケーションクラス。"""

    def __init__(self) -> None:
        """GUI アプリケーションの構築と初期設定を行います。"""
        super().__init__()

        # ── [ステップ1] ウィンドウ設定 ──
        self.title("画像ファイルリアルタイム監視ツール")
        self.geometry("750x500")

        self.observer_instance: Optional[Observer] = None
        self.is_monitoring: bool = False

        # ── [ステップ2] 画面要素（UI）のレイアウト作成 ──
        # ディレクトリ選択用のフレーム設定
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

        # 操作用ボタンの配置（開始 / 停止）
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
        self.stop_button.pack(side=tk.LEFT)

        # ログ出力用 ScrolledText ウィジェット
        self.log_text_widget = scrolledtext.ScrolledText(
            self, state="normal", wrap=tk.WORD
        )
        self.log_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # ── [ステップ3] 標準出力のリダイレクト化 ──
        # print文の出力をログ用テキストエリアに向ける
        sys.stdout = TextRedirector(self.log_text_widget)

        # ウィンドウを閉じるイベントのフック設定
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

    def select_directory_path(self) -> None:
        """フォルダ選択ダイアログを表示し、選択結果をテキストボックスに反映します。"""
        selected_path = filedialog.askdirectory(
            initialdir=self.directory_path_variable.get()
        )
        if selected_path:
            self.directory_path_variable.set(selected_path)

    def start_monitoring(self) -> None:
        """監視スレッドを立ち上げ、ファイル監視処理を開始します。"""
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

        # ── [ステップ2] watchdog 監視スレッドの開始 ──
        event_handler = ImageFileEventHandler(
            watch_extensions=TARGET_FILE_EXTENSIONS,
            debounce_interval=DEBOUNCE_INTERVAL_SECONDS,
        )
        self.observer_instance = Observer()
        self.observer_instance.schedule(
            event_handler, path=target_directory_path, recursive=False
        )
        self.observer_instance.start()

        print("=" * 70)
        print("ディレクトリの監視を開始しました...")
        print(f"  ・対象ディレクトリ: {target_directory_path}")
        print(f"  ・対象拡張子      : {', '.join(TARGET_FILE_EXTENSIONS)}")
        print(f"  ・デバウンス間隔  : {DEBOUNCE_INTERVAL_SECONDS} 秒")
        print("=" * 70)

    def stop_monitoring(self) -> None:
        """ファイル監視を安全に停止します。"""
        if self.observer_instance and self.is_monitoring:
            # ── [ステップ1] Observer の停止とクリーンアップ ──
            self.observer_instance.stop()
            self.observer_instance.join()
            self.observer_instance = None
            self.is_monitoring = False

            # ── [ステップ2] UI状態の復元 ──
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

            print("監視を停止しました。")

    def on_close_window(self) -> None:
        """アプリ終了時に監視スレッドを確実に停止させてからウィンドウを閉じます。"""
        if self.is_monitoring:
            self.stop_monitoring()
        self.destroy()


def main() -> None:
    """メイン処理を実行し、tkinter GUIを立ち上げます。"""
    app = DirectoryWatcherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
