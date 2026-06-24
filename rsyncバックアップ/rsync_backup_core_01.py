import time
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import re
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
"""

# ==========================================
# 設定: グローバル変数
# ==========================================
BACKUP_SOURCE_DIR: str = "/home/vm/workspace/_test_rsync_202604/src"
BACKUP_DESTINATION_DIR: str = "/home/vm/workspace/_test_rsync_202604/dst/"

EXCLUDE_FILESIZE_MB: int = 10
EXCLUDE_FILE_EXTENTION: str = "bak,tmp"


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
        self.root.title("Rsync Backup Tool")
        self.root.geometry("500x200")

        # 1行目: ディレクトリ名表示用 (新規追加)
        self.label_dir: tk.Label = tk.Label(
            root, text="", anchor="w", justify="left", wraplength=450)
        self.label_dir.pack(fill="x", padx=20, pady=(10, 0))

        # 2行目: ファイル名・状態表示用 (既存の名前を維持)
        self.label: tk.Label = tk.Label(
            root,
            text="準備中...",
            anchor="w",
            justify="left",
            wraplength=450)
        self.label.pack(fill="x", padx=20, pady=(0, 10))

        self.progress: ttk.Progressbar = ttk.Progressbar(
            root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

        self.cancel_button: tk.Button = tk.Button(
            root, text="中断", command=self.stop_backup, state=tk.DISABLED)
        self.cancel_button.pack(pady=5)

        self.process: Optional[subprocess.Popen] = None
        self.is_running: bool = False

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
            self.root.after(0, self.finish_backup, "エラー",
                            f"バックアップ元が見つかりません:\n{BACKUP_SOURCE_DIR}")
            return False

        if not os.path.isdir(BACKUP_SOURCE_DIR):
            self.root.after(0, self.finish_backup, "エラー",
                            f"指定されたパスはディレクトリではありません:\n{BACKUP_SOURCE_DIR}")
            return False

        # バックアップ先ディレクトリの親ディレクトリ存在チェック
        # (バックアップ先自体はrsyncが作成可能だが、その親がないと失敗するため)
        dest_parent = os.path.dirname(BACKUP_DESTINATION_DIR.rstrip('/'))
        if dest_parent and not os.path.exists(dest_parent):
            self.root.after(0, self.finish_backup, "エラー",
                            f"バックアップ先の保存親フォルダが存在しません:\n{dest_parent}")
            return False

        return True

    def prepare_backup(self) -> None:
        """rsyncのドライラン(-avhin)を実行して対象ファイル数を集計し、ユーザーに開始確認を求める。
        """

        self.label.config(text="バックアップ対象をスキャン中...")

        exclude_exts: List[str] = [ext.strip() for ext in EXCLUDE_FILE_EXTENTION.split(',')]
        exclude_args: List[str] = [f"--exclude=*.{ext}" for ext in exclude_exts]

        # --out-format=%n により、変更対象のファイルパスのみを1行ずつ出力させる
        cmd: List[str] = [
            "rsync", "-avhin",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
            BACKUP_SOURCE_DIR.rstrip('/') + '/',
            BACKUP_DESTINATION_DIR.rstrip('/') + '/'
        ]

        try:
            # ドライラン実行
            result: subprocess.CompletedProcess = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )

            # 出力行文字列の先頭2文字からファイル転送フラグ ">f" を探す
            lines: List[str] = result.stdout.splitlines()
            target_files: int = 0
            for line in lines:
                if line.startswith(">f"):
                    target_files += 1

            confirm_msg: str = (
                f"バックアップを開始しますか？\n\n"
                f"コピー元: {BACKUP_SOURCE_DIR}\n"
                f"コピー先: {BACKUP_DESTINATION_DIR}\n\n"
                f"バックアップ対象ファイル数: {target_files} 件\n"
                f"（サイズ制限: {EXCLUDE_FILESIZE_MB}MB以下）"
            )

            if target_files == 0:
                messagebox.showinfo("情報", "同期が必要なファイルはありません。")
                self.root.destroy()
                return

            if messagebox.askyesno("バックアップ開始の確認", confirm_msg):
                self.is_running = True
                self.cancel_button.config(state=tk.NORMAL)
                # 本番のrsyncを実行
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

        exclude_exts: List[str] = [ext.strip() for ext in EXCLUDE_FILE_EXTENTION.split(',')]
        exclude_args: List[str] = [f"--exclude=*.{ext}" for ext in exclude_exts]

        # -i (--itemize-changes) を追加して、転送された項目を判別しやすくする
        cmd: List[str] = [
            "rsync", "-avhi",
            f"--max-size={EXCLUDE_FILESIZE_MB}m",
            *exclude_args,
            BACKUP_SOURCE_DIR.rstrip('/') + '/',
            BACKUP_DESTINATION_DIR.rstrip('/') + '/'
        ]

        completed_count: int = 0

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

                    # デバッグ用ウェイト
                    time.sleep(0.5)

                    # -i オプションにより、ファイル転送時は行の先頭が ">f" などになる
                    # これをトリガーに「ファイル1つ完了」とみなす
                    # ※ディレクトリ作成 "cd"や 既存ディレクトリにコピー ".d" はカウントしない
                    if line.startswith('>f'):
                        completed_count += 1

                        # 進捗率の計算 (target_filesが0の場合の除算エラー回避)
                        if target_files > 0:
                            percent: int = int((completed_count / target_files) * 100)
                            # 100%を超えないよう制御
                            percent = min(percent, 100)
                            self.root.after(0, self.update_progress, percent)

                        # パスの解析
                        # ">f+++++++ path/to/file" からパス部分を抽出
                        parts = line.strip().split(' ', 1)
                        full_path = parts[1] if len(parts) > 1 else ""

                        # ディレクトリとファイル名に分割
                        dir_name, file_name = os.path.split(full_path)

                        # 表示の更新
                        self.root.after(0, self.label_dir.config, {"text": f"フォルダ: {dir_name}"})
                        self.root.after(
                            0, self.label.config, {
                                "text": f"コピー中 ({completed_count}/{target_files}): {file_name}"})

                        # 処理中のファイル名を表示
                        # filename: str = line.strip().split('/')[-1]
                        # self.root.after(
                        #     0, self.label.config, {
                        #         "text": f"コピー中 ({completed_count}/{target_files}):\n{filename}"})

            self.process.wait()

            if self.is_running and self.process.returncode == 0:
                # 最終的に100%にする
                self.root.after(0, self.update_progress, 100)
                self.root.after(0, self.finish_backup, "完了", "正常に完了しました。")
            elif self.is_running and self.process.returncode != 0:
                self.root.after(
                    0,
                    self.finish_backup,
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

    def finish_backup(self, title: str, message: str) -> None:
        """終了メッセージを表示してアプリケーションを閉じる。

        Args:
            title (str): ダイアログのタイトル。
            message (str): 表示するメッセージ内容。
        """
        messagebox.showinfo(title, message)
        self.root.destroy()


if __name__ == "__main__":
    root: tk.Tk = tk.Tk()
    app: BackupApp = BackupApp(root)
    root.mainloop()
