import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
from typing import Optional, List

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
"""

# ==========================================
# 設定: グローバル変数
# ==========================================
BACKUP_SOURCE_DIR: str = "/home/vm/workspace/_test_rsync_202604/src"
BACKUP_DESTINATION_DIR: str = "/home/vm/workspace/_test_rsync_202604/dst/"

EXCLUDE_FILESIZE_MB: int = 10
EXCLUDE_FILE_EXTENSION: str = "bak,tmp"

FLAG_DEBUG_WAIT: bool = True


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
        """

        self.label.config(text="バックアップ対象をスキャン中...")

        exclude_exts: List[str] = [ext.strip() for ext in EXCLUDE_FILE_EXTENSION.split(',')]
        exclude_args: List[str] = [f"--exclude=*.{ext}" for ext in exclude_exts]

        # -i (--itemize-changes) を追加して、転送された項目を判別できるようにする
        cmd: List[str] = [
            "rsync", "-avhin",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
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

            # カスタムダイアログの表示（プレビュー機能）
            dialog = PreviewDialog(
                self.root,
                "バックアップの開始確認とプレビュー",
                confirm_msg,
                result.stdout,  # ドライランの結果を渡す
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

        # -i (--itemize-changes) を追加して、転送された項目を判別できるようにする
        cmd: List[str] = [
            "rsync", "-avhi",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
            BACKUP_SOURCE_DIR.rstrip('/') + '/',
            BACKUP_DESTINATION_DIR.rstrip('/') + '/'
        ]

        completed_count: int = 0
        self.full_log = ""  # ログを初期化

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
                if self.process.returncode == 0:
                    self.root.after(0, self.update_progress, 100)
                    success_msg = f"正常に完了しました。\n(バックアップ対象ファイル数: {target_files} 件)"
                    self.root.after(0, self.show_final_log, "バックアップ完了", success_msg)
                else:
                    self.root.after(
                        0,
                        self.show_final_log,
                        "エラー",
                        f"rsyncエラーが発生しました。(Code: {self.process.returncode})")

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
        """

        if messagebox.askyesno("中断確認", "バックアップを中断して終了しますか？"):
            self.is_running = False
            if self.process:
                self.process.terminate()
            self.root.destroy()

    def show_final_log(self, title: str, message: str) -> None:
        """完了後にログを閲覧できるウィンドウを表示する。"""
        PreviewDialog(self.root, title, message, self.full_log, show_start_button=False)
        self.root.destroy()

    def finish_backup(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)
        self.root.destroy()


if __name__ == "__main__":
    root: tk.Tk = tk.Tk()
    app: BackupApp = BackupApp(root)
    root.mainloop()
