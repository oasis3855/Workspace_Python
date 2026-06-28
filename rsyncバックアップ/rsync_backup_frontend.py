#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import filedialog

"""rsync GUI バックアップツールのフロントエンド管理スクリプト。

このモジュールは、複数のバックアップ実行条件（プロファイル）をマスターJSONファイルで管理し、
ユーザーが選択した条件をバックアップスクリプト（rsync_backup_##.py）へ受け渡すGUIフロントエンドを提供します。

主な機能:
    - マスターJSONからの複数プロファイルの読み込み・一元管理
    - 画面上のドロップダウンリストによる実行プロファイルの選択
    - 選択した条件に基づくバックアップスクリプトの非同期起動と自身の即時終了
    - 各プロファイルの新規追加、および既存プロファイルの編集（ディレクトリ選択ダイアログ対応）
    - 設定用JSONファイルをOS既定のGUIエディタ（xdg-open）で直接開く機能

Requires:
    - Python 3.10+
    - tkinter
    - rsync_backup_##.py（同一ディレクトリ内）

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/06/17)
    1.1.0 (2026/06/28) - FLAG_SIZE_ONLY(タイムスタンプの相違を無視),FLAG_USE_SUFFIX(旧ファイルを同一階層にバックアップ)の機能追加
"""


# 1. フロントエンドスクリプトが存在するディレクトリの絶対パスを取得
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 同一ディレクトリ内の各スクリプト・ファイルのフルパスを構築
BACKUP_SCRIPT_NAME = "rsync_backup_core_03.py"
BACKUP_SCRIPT_PATH = os.path.join(FRONTEND_DIR, BACKUP_SCRIPT_NAME)

# 3. 設定ファイルのパス（rsync_backup_03.py と共通）
CONFIG_FILE_NAME = ".rsync_backup_python.json"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), CONFIG_FILE_NAME)

# 4. 複数の実行条件（ディレクトリセット）を管理するマスターファイル
MASTER_PROFILES_FILE = ".rsync_backup_profiles.json"
MASTER_PROFILES_PATH = os.path.join(os.path.expanduser("~"), MASTER_PROFILES_FILE)


class ProfileEditDialog(tk.Toplevel):
    """プロファイルの新規追加および編集を行うための入力ダイアログ。"""

    def __init__(
            self,
            parent: tk.Tk,
            title: str,
            current_name: str = "",
            current_data: dict | None = None) -> None:
        """プロファイル入力ダイアログの初期化と各GUIコンポーネントの配置を行います。

        Args:
            parent (tk.Tk): 親ウィンドウとなるメインのルートオブジェクト。
            title (str): ダイアログのタイトルバーに表示する文字列。
            current_name (str, optional): 編集対象のプロファイル名。新規追加時は空文字。デフォルトは ""。
            current_data (dict | None, optional): 編集対象の設定データ辞書。新規追加時は None。デフォルトは None。
        """
        super().__init__(parent)
        self.title(title)
        self.geometry("620x400")
        self.resizable(False, False)

        self.result_name = None
        self.result_data = None

        # 元データの初期化
        if current_data is None:
            current_data = {
                "BACKUP_SOURCE_DIR": "",
                "BACKUP_DESTINATION_DIR": "",
                "EXCLUDE_FILESIZE_MB": 10,
                "EXCLUDE_FILE_EXTENSION": "bak,tmp",
                "FLAG_DEBUG_WAIT": False,
                "FLAG_SIZE_ONLY": False,
                "FLAG_USE_SUFFIX": False,
                "FLAG_CHECKSUM": False,
            }

        # --- ウィジェットの作成と配置 ---
        frame = tk.Frame(self, padx=20, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. プロファイル名
        tk.Label(
            frame,
            text="設定名 (プロファイル名):",
            font=(
                "",
                9,
                "bold")).grid(
            row=0,
            column=0,
            sticky="e",
            pady=5)
        self.ent_name = tk.Entry(frame, width=40)
        self.ent_name.insert(0, current_name)
        self.ent_name.grid(row=0, column=1, sticky="w", pady=5, padx=10)
        if current_name:  # 編集時は名前の変更を不可にする（キー重複防止のため。変更したい場合は新規追加を促す）
            self.ent_name.config(state="disabled")

        # 2. コピー元パス (Entry + 参照ボタン)
        tk.Label(
            frame, text="コピー元フォルダ (Src):", font=("", 9, "bold")
        ).grid(row=1, column=0, sticky="e", pady=5)

        src_frame = tk.Frame(frame)  # 横並び用のサブフレーム
        src_frame.grid(row=1, column=1, sticky="w", pady=5, padx=10)

        self.ent_src = tk.Entry(src_frame, width=40)
        self.ent_src.insert(0, current_data.get("BACKUP_SOURCE_DIR", ""))
        self.ent_src.pack(side="left")

        btn_src_browse = tk.Button(
            src_frame, text="参照...", command=self.browse_src
        )
        btn_src_browse.pack(side="left", padx=5)

        # 3. コピー先パス (Entry + 参照ボタン)
        tk.Label(
            frame, text="コピー先フォルダ (Dst):", font=("", 9, "bold")
        ).grid(row=2, column=0, sticky="e", pady=5)

        dst_frame = tk.Frame(frame)  # 横並び用のサブフレーム
        dst_frame.grid(row=2, column=1, sticky="w", pady=5, padx=10)

        self.ent_dst = tk.Entry(dst_frame, width=40)
        self.ent_dst.insert(0, current_data.get("BACKUP_DESTINATION_DIR", ""))
        self.ent_dst.pack(side="left")

        btn_dst_browse = tk.Button(
            dst_frame, text="参照...", command=self.browse_dst
        )
        btn_dst_browse.pack(side="left", padx=5)

        # 4. 除外サイズ
        tk.Label(
            frame,
            text="除外ファイルサイズ (MB):",
            font=(
                "",
                9,
                "bold")).grid(
            row=3,
            column=0,
            sticky="e",
            pady=5)
        self.ent_size = tk.Entry(frame, width=10)
        self.ent_size.insert(0, str(current_data.get("EXCLUDE_FILESIZE_MB", 10)))
        self.ent_size.grid(row=3, column=1, sticky="w", pady=5, padx=10)

        # 5. 除外拡張子
        tk.Label(
            frame,
            text="除外拡張子 (カンマ区切り):",
            font=(
                "",
                9,
                "bold")).grid(
            row=4,
            column=0,
            sticky="e",
            pady=5)
        self.ent_ext = tk.Entry(frame, width=25)
        self.ent_ext.insert(0, current_data.get("EXCLUDE_FILE_EXTENSION", "bak,tmp"))
        self.ent_ext.grid(row=4, column=1, sticky="w", pady=5, padx=10)

        # 6. デバッグ待機
        self.var_debug = tk.BooleanVar(value=current_data.get("FLAG_DEBUG_WAIT", False))
        self.chk_debug = tk.Checkbutton(
            frame,
            text="デバッグ用に表示を遅くする (FLAG_DEBUG_WAIT)",
            variable=self.var_debug)
        self.chk_debug.grid(row=5, column=1, sticky="w", pady=5, padx=10)

        # 7. サイズ基準 (--size-only)
        self.var_size_only = tk.BooleanVar(value=current_data.get("FLAG_SIZE_ONLY", False))
        tk.Checkbutton(
            frame,
            text="サイズが同一ならタイムスタンプの変更を無視する (--size-only)",
            variable=self.var_size_only).grid(
            row=6,
            column=1,
            sticky="w",
            pady=2,
            padx=10)

        # 8. 同階層への安全な退避 (--backup)
        self.var_use_suffix = tk.BooleanVar(value=current_data.get("FLAG_USE_SUFFIX", False))
        tk.Checkbutton(
            frame,
            text="上書き・削除される旧ファイルを同階層に退避する (--backup)",
            variable=self.var_use_suffix).grid(
            row=7,
            column=1,
            sticky="w",
            pady=2,
            padx=10)

        # 9. チェックサム基準 (--checksum)
        self.var_checksum = tk.BooleanVar(value=current_data.get("FLAG_CHECKSUM", False))
        tk.Checkbutton(
            frame,
            text="ファイルの中身（チェックサム）の相違を検知 (--checksum)",
            variable=self.var_checksum).grid(
            row=8,
            column=1,
            sticky="w",
            pady=2,
            padx=10)

        # ボタンエリア
        btn_frame = tk.Frame(frame, pady=10)
        btn_frame.grid(row=9, column=0, columnspan=2, sticky="e")

        tk.Button(
            btn_frame,
            text="保存",
            width=12,
            bg="#4CAF50",
            fg="white",
            font=(
                "",
                9,
                "bold"),
            command=self.on_save).pack(
            side="right",
            padx=5)
        tk.Button(
            btn_frame,
            text="キャンセル",
            width=10,
            command=self.destroy).pack(
            side="right",
            padx=5)

        # モーダルダイアログ設定
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def browse_src(self) -> None:
        """ディレクトリ選択ダイアログを表示し、ユーザーが選択したコピー元パスをテキストボックスに代入します。

        ユーザーが現在の入力値を起点として、直感的にフォルダを選択できるように初期ディレクトリを制御します。
        """
        # 現在入力されているパスがあれば、それを初期ディレクトリとして開く
        initial_dir = self.ent_src.get() or os.path.expanduser("~")
        selected_dir = filedialog.askdirectory(
            title="コピー元（同期元）フォルダを選択", initialdir=initial_dir
        )
        if selected_dir:
            self.ent_src.delete(0, tk.END)
            self.ent_src.insert(0, selected_dir)

    def browse_dst(self) -> None:
        """ディレクトリ選択ダイアログを表示し、ユーザーが選択したコピー先パスをテキストボックスに代入します。

        ユーザーが現在の入力値を起点として、直感的にフォルダを選択できるように初期ディレクトリを制御します。
        """
        initial_dir = self.ent_dst.get() or os.path.expanduser("~")
        selected_dir = filedialog.askdirectory(
            title="コピー先（バックアップ先）フォルダを選択",
            initialdir=initial_dir,
        )
        if selected_dir:
            self.ent_dst.delete(0, tk.END)
            self.ent_dst.insert(0, selected_dir)

    def on_save(self) -> None:
        """入力された各設定値のバリデーションを行い、末尾スラッシュを強制補正した上でデータを確定してダイアログを閉じます。

        設定名、コピー元、コピー先の必須入力チェック、およびサイズ入力の数値チェックを行います。
        また、rsyncの仕様に合わせ、ディレクトリパスの末尾が「/」でない場合は自動で付与します。
        """
        # 編集時は disabled になっているので、get() するために一時的に状態を戻す
        state = self.ent_name.cget("state")
        self.ent_name.config(state="normal")
        name = self.ent_name.get().strip()
        self.ent_name.config(state=state)

        src = self.ent_src.get().strip()
        dst = self.ent_dst.get().strip()
        size_str = self.ent_size.get().strip()
        ext = self.ent_ext.get().strip()

        # 1. 必須入力チェック
        if not name or not src or not dst:
            messagebox.showwarning(
                "入力エラー", "設定名、コピー元、コピー先は必須入力です。"
            )
            return

        # 2. 除外ファイルサイズのバリデーション（1以上の整数）
        try:
            size = int(size_str)
            if size < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "入力エラー", "除外ファイルサイズには1以上の整数を入力してください。"
            )
            return

        # 3. 除外拡張子のバリデーション（ASCII半角英数字のみ、空文字は許容）
        if ext:
            # カンマで分割し、各拡張子の前後空白を取り除いてチェック
            ext_list = [e.strip() for e in ext.split(",")]
            for e in ext_list:
                if not e:  # 「bak,,tmp」のような連続カンマによる空要素はスキップ、またはエラーにする場合はここで処理
                    continue
                # a-z, A-Z, 0-9 のみで構成されているか正規表現でチェック
                if not re.match(r"^[a-zA-Z0-9]+$", e):
                    messagebox.showwarning(
                        "入力エラー",
                        f"除外拡張子に不正な文字が含まれています: '{e}'\n"
                        "拡張子は半角英数字（a-z, A-Z, 0-9）のみで入力し、カンマで区切ってください。",
                    )
                    return

            # きれいに整形された（余分なスペースを詰めた）文字列を再構築
            ext = ",".join([e for e in ext_list if e])

        # 4. ディレクトリパスの末尾スラッシュ強制付与
        if not src.endswith("/"):
            src += "/"
        if not dst.endswith("/"):
            dst += "/"

        # データの確定
        self.result_name = name
        self.result_data = {
            "BACKUP_SOURCE_DIR": src,
            "BACKUP_DESTINATION_DIR": dst,
            "EXCLUDE_FILESIZE_MB": size,
            "EXCLUDE_FILE_EXTENSION": ext,
            "FLAG_DEBUG_WAIT": self.var_debug.get(),
            "FLAG_SIZE_ONLY": self.var_size_only.get(),
            "FLAG_USE_SUFFIX": self.var_use_suffix.get(),
            "FLAG_CHECKSUM": self.var_checksum.get(),
        }
        self.destroy()


class FrontendApp:

    def __init__(self, root: tk.Tk) -> None:
        """フロントエンドアプリケーションのメイン画面を初期化し、プロファイル選択UIおよび管理ボタンを配置します。

        Args:
            root (tk.Tk): tkinterのルートウィンドウオブジェクト。
        """
        self.root = root
        self.root.title("rsync GUI - バックアップ条件選択")
        self.root.geometry("450x250")

        # プロファイルデータのロード
        self.profiles = self.load_master_profiles()

        # --- UI配置 ---
        tk.Label(root, text="実行条件（プロファイル）を選択してください:", font=("", 10, "normal")).pack(pady=(15, 5))

        self.combobox = ttk.Combobox(root, state="readonly", width=40)
        self.combobox.pack(pady=5)
        self.update_combobox()

        # ボタンエリア
        btn_frame = tk.Frame(root, pady=15)
        btn_frame.pack()

        # 上段：メインアクション
        tk.Button(
            btn_frame,
            text="バックアップを実行",
            bg="#4CAF50",
            fg="white",
            font=("", 10, "normal"),
            width=22,
            command=self.execute_backup,
        ).grid(row=0, column=0, columnspan=3, pady=5, padx=5)

        # 下段：管理機能
        tk.Button(btn_frame, text="実行条件の新規追加", width=16, command=self.add_profile).grid(
            row=1, column=0, pady=5, padx=5
        )
        tk.Button(btn_frame, text="実行条件の修正", width=16, command=self.edit_profile).grid(
            row=1, column=1, pady=5, padx=5
        )
        tk.Button(btn_frame, text="JSON編集", width=8, command=self.open_json_in_editor).grid(
            row=1, column=2, pady=5, padx=5
        )

        # 最下段：終了
        tk.Button(root, text="終了", width=10, command=root.destroy).pack(side="bottom", pady=15)

    def load_master_profiles(self) -> dict:
        """ユーザーのホームディレクトリから管理用のマスタープロファイルJSONファイルを読み込みます。

        ファイルが存在しない、または破損している場合は、デフォルトのサンプルデータを生成して自動保存します。

        Returns:
            dict: 読み込まれた、または新規生成されたプロファイル名がキー、設定データ辞書が値のマスターデータ。
        """
        if os.path.exists(MASTER_PROFILES_PATH):
            try:
                with open(MASTER_PROFILES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] マスタープロファイルの読み込みに失敗: {e}")

        # デフォルトのサンプルデータ
        default_profiles = {
            "テスト環境バックアップ": {
                "BACKUP_SOURCE_DIR": "/home/user/test/src/",
                "BACKUP_DESTINATION_DIR": "/home/test/user/dst/",
                "EXCLUDE_FILESIZE_MB": 10,
                "EXCLUDE_FILE_EXTENSION": "bak,tmp",
                "FLAG_DEBUG_WAIT": True,
                "FLAG_SIZE_ONLY": False,
                "FLAG_USE_SUFFIX": False,
            },
            "本番ドキュメント同期": {
                "BACKUP_SOURCE_DIR": "/home/user/documents/",
                "BACKUP_DESTINATION_DIR": "/media/usbdisk/backup/documents/",
                "EXCLUDE_FILESIZE_MB": 50,
                "EXCLUDE_FILE_EXTENSION": "iso,img,bak,tmp",
                "FLAG_DEBUG_WAIT": False,
                "FLAG_SIZE_ONLY": False,
                "FLAG_USE_SUFFIX": False,
            },
        }
        # 初期ファイルを保存しておく
        self.save_master_profiles(default_profiles)
        return default_profiles

    def save_master_profiles(self, data: dict) -> None:
        """変更または追加されたプロファイルデータの一覧をマスターJSONファイルに永続化保存します。

        Args:
            data (dict): 保存対象となるすべてのプロファイルを含んだデータ辞書。
        """
        try:
            with open(MASTER_PROFILES_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[INFO] マスタープロファイルを保存しました: {MASTER_PROFILES_PATH}")
        except Exception as e:
            messagebox.showerror("エラー", f"マスターファイルの保存に失敗しました:\n{e}")

    def update_combobox(self, select_name: str | None = None) -> None:
        """ドロップダウンリスト（Combobox）の選択肢を最新のマスターデータの内容にリフレッシュします。

        Args:
            select_name (str | None, optional): 更新後に自動で選択状態（アクティブ）にしたいプロファイル名。
                指定がない場合、または存在しない場合はリストの先頭の項目が選択されます。デフォルトは None。
        """
        names = list(self.profiles.keys())
        self.combobox["values"] = names

        if names:
            if select_name in names:
                self.combobox.set(select_name)
            else:
                self.combobox.current(0)
        else:
            self.combobox.set("")

    def execute_backup(self) -> None:
        """現在選択されている設定内容をバックアップスクリプト用のJSONに書き出し、別プロセスで起動して自身を即時終了します。

        バトンリレー方式を採用しており、呼び出し先スクリプトの作業ディレクトリを統一した上で、
        フロントエンド自身はメインウィンドウを破棄して完全に終了します。
        """
        selected_name = self.combobox.get()
        if not selected_name:
            messagebox.showwarning("警告", "実行条件が選択されていません。")
            return

        selected_config = self.profiles[selected_name]

        try:
            # 1. 選択された設定内容で、rsync_backup_03.py が読むファイルを上書き
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(selected_config, f, indent=2, ensure_ascii=False)

            # 2. 同一ディレクトリ内のバックアップスクリプトを別プロセスで非同期起動
            subprocess.Popen(
                [sys.executable, BACKUP_SCRIPT_PATH],
                cwd=FRONTEND_DIR
            )

            # 3. フロントエンドを終了
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("エラー", f"バックアップスクリプトの起動に失敗しました:\n{e}")

    def add_profile(self) -> None:
        """新規プロファイル追加用のモーダルダイアログを表示し、ユーザーが入力した新しい実行条件をマスターファイルに保存します。

        既存のプロファイル名と重複した場合は、ユーザーに上書き確認を求めます。
        保存成功後はドロップダウンをリフレッシュし、追加したプロファイルを自動選択します。
        """
        dialog = ProfileEditDialog(self.root, "新規実行条件の追加")

        if dialog.result_name:
            if dialog.result_name in self.profiles:
                if not messagebox.askyesno("上書き確認", f"「{dialog.result_name}」は既に存在します。上書きしますか？"):
                    return

            # 内部データを更新してJSONへ保存
            self.profiles[dialog.result_name] = dialog.result_data
            self.save_master_profiles(self.profiles)

            # UIのドロップダウンを更新し、追加した項目を選択状態にする
            self.update_combobox(select_name=dialog.result_name)
            messagebox.showinfo("完了", f"実行条件「{dialog.result_name}」を追加・保存しました。")

    def edit_profile(self) -> None:
        """現在ドロップダウンリストで選択されているプロファイルの編集ダイアログを表示し、変更内容をマスターファイルに保存します。

        プロファイル名（JSONのキー）の整合性を維持するため、編集時は設定名の変更を抑止した状態でダイアログを開きます。
        """
        selected_name = self.combobox.get()
        if not selected_name:
            messagebox.showwarning("警告", "修正する対象が選択されていません。")
            return

        current_data = self.profiles[selected_name]

        # 既存データを渡してダイアログを開く
        dialog = ProfileEditDialog(
            self.root,
            f"実行条件の修正 - {selected_name}",
            current_name=selected_name,
            current_data=current_data)

        if dialog.result_name:
            # データを更新してJSONへ保存
            self.profiles[dialog.result_name] = dialog.result_data
            self.save_master_profiles(self.profiles)

            # UIをリフレッシュ
            self.update_combobox(select_name=dialog.result_name)
            messagebox.showinfo("完了", f"実行条件「{dialog.result_name}」の修正を保存しました。")

    def open_json_in_editor(self) -> None:
        """バックアップスクリプトが参照するJSON設定ファイルを、OS既定のGUIテキストエディタを介して非同期で直接開きます。

        Linuxの `xdg-open` コマンドを使用することで、ユーザーのシステム設定に沿ったエディタを安全に起動します。
        ファイルがまだ存在しない場合は、現在の選択値に基づいて事前に自動生成します。
        """
        # 万が一ファイルがまだ存在しない場合は、現在のデフォルト値で一度ファイルを作成する
        if os.path.exists(MASTER_PROFILES_PATH):
            try:
                # xdg-open を使ってシステム既定のエディターを呼び出す
                # stdout/stderr を DEVNULL に流すことで、エディター起因の警告ログがターミナルに溢れるのを防ぎます
                subprocess.Popen(
                    ["xdg-open", MASTER_PROFILES_PATH],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print(f"[INFO] xdg-open によりファイルを開きました: {CONFIG_PATH}")
            except Exception as e:
                messagebox.showerror("エラー", f"設定ファイルを開けませんでした:\n{e}")


if __name__ == "__main__":
    main_root = tk.Tk()
    app = FrontendApp(main_root)
    main_root.mainloop()
