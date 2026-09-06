#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""画像のサムネイル生成・HTMLテーブル構築およびCSV相互変換を行う対話型ユーティリティスクリプト。

このモジュールは、指定ディレクトリ内のJPG画像から長辺基準のサムネイル画像を自動生成し、
Exifメタデータ（撮影日時）の抽出および各種情報（ディレクトリ名、ファイル名、撮影地、コメント、フラグ等）を
保持したHTMLテーブルを構築・更新します。
既存HTMLの読み込みによるメタデータ引き継ぎ、消失ファイルへの「[削除]」タグ自動付与、
並びにHTMLとCSV間の双方向変換機能を備えており、画像の整理・管理を統合的にサポートします。

Attributes:
    DEFAULT_INITIAL_DIRECTORY (Path): GUIダイアログ表示時の初期表示ディレクトリ（デフォルト: ホームディレクトリ）。
    DEFAULT_THUMBNAIL_DIRECTORY_NAME (str): サムネイル画像の保存先サブディレクトリ名（デフォルト: "thumb"）。
    DEFAULT_THUMBNAIL_LONG_EDGE_PX (int): 生成するサムネイル画像の長辺サイズ（デフォルト: 180px）。
    DEFAULT_FILENAME_MAX_LENGTH (int): ファイル名表示時の最大文字数制限（デフォルト: 10文字）。
    DEFAULT_TABLE_EDITOR_JS_PATH (str): HTML内で読み込むJavaScriptファイルのパス（デフォルト: "table_editor.js"）。
    DEFAULT_UPDATE_EXIF_DATE (bool): Exif再読み込みによる日時更新の既定値（デフォルト: True）。
    DEFAULT_OVERWRITE_THUMBNAIL (bool): 既存サムネイルの強制上書き生成の既定値（デフォルト: False）。

Requires:
    - Python 3.8+
    - Pillow (PIL): 画像処理・Exifデータ解析・リサイズ用ライブラリ (pip install Pillow)
    - beautifulsoup4: HTMLテーブル解析用ライブラリ (pip install beautifulsoup4)
    - tkinter: ファイル／ディレクトリ選択用GUIツールキット（Python標準ライブラリ）

Author:
    Google Gemini 3.6 Flash Collaborating Coding

Version:
    1.0.0 (2026/08/30)
    1.1.0 (2026/09/06) サムネイル画像生成,Exif撮影日時読み込みの既定値を変更
"""

import csv
from datetime import datetime
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import filedialog
from typing import Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup
from PIL import ExifTags, Image, ImageOps

# ── [グローバル設定] 設定のデフォルト値を定義 ──
DEFAULT_INITIAL_DIRECTORY: Path = Path.home()
DEFAULT_THUMBNAIL_DIRECTORY_NAME: str = "thumb"
DEFAULT_THUMBNAIL_LONG_EDGE_PX: int = 180
DEFAULT_FILENAME_MAX_LENGTH: int = 10
DEFAULT_TABLE_EDITOR_JS_PATH: str = "table_editor.js"
DEFAULT_UPDATE_EXIF_DATE: bool = True
DEFAULT_OVERWRITE_THUMBNAIL: bool = False


def create_backup_file(target_file_path: Path) -> Optional[Path]:
    """
    対象ファイルが存在する場合、連番の拡張子 (.bak001, .bak002 ...) を付与してバックアップを作成する。

    Args:
        target_file_path (Path): バックアップ対象のファイルパス

    Returns:
        Optional[Path]: 作成されたバックアップファイルのパス（存在しない場合は None）
    """
    # ── [ステップ1] ファイルの存在確認 ──
    if not target_file_path.exists():
        return None

    # ── [ステップ2] 空き連番番号（001, 002...）の検索 ──
    counter = 1
    while True:
        backup_path = target_file_path.with_name(
            f"{target_file_path.name}.bak{counter:03d}"
        )
        if not backup_path.exists():
            break
        counter += 1

    # ── [ステップ3] バックアップファイルの複製（コピー）実行 ──
    shutil.copy2(target_file_path, backup_path)
    print(f"バックアップを作成しました: {backup_path.name}")

    return backup_path


def format_display_filename(
    filename: str, max_length: int = DEFAULT_FILENAME_MAX_LENGTH
) -> str:
    """
    ファイル名から拡張子を除去し、指定文字数を超える場合は末尾を省略記号にする。

    Args:
        filename (str): 元のファイル名（例: "DSC_123456789.jpg"）
        max_length (int): 省略せずに表示する最大文字数

    Returns:
        str: 成形後の文字列（例: "DSC_123456..."）
    """
    # ── [ステップ1] 拡張子の除去 ──
    stem_name = Path(filename).stem

    # ── [ステップ2] 文字数チェックと省略表記の適用 ──
    if len(stem_name) > max_length:
        return f"{stem_name[:max_length]}..."

    return stem_name


def select_directory_via_dialog(
    title_message: str, initial_dir: Path = DEFAULT_INITIAL_DIRECTORY
) -> Optional[Path]:
    """
    GUIダイアログを表示して、ユーザーにディレクトリを選択させる。

    Args:
        title_message (str): ダイアログのタイトルバーに表示するメッセージ
        initial_dir (Path): ダイアログを開く際の初期表示ディレクトリ

    Returns:
        Optional[Path]: 選択されたディレクトリのパス（キャンセルの場合はNone）
    """
    # ── [ステップ1] ダイアログ表示用のTkinterルートウィンドウ初期化 ──
    root_window = tk.Tk()
    root_window.withdraw()
    root_window.attributes("-topmost", True)

    # ── [ステップ2] フォルダ選択ダイアログの起動 ──
    selected_path_str = filedialog.askdirectory(
        title=title_message, initialdir=str(initial_dir)
    )

    # ── [ステップ3] ウィンドウ破棄と結果返却 ──
    root_window.destroy()

    if not selected_path_str:
        return None

    return Path(selected_path_str)


def select_file_via_dialog(
    title_message: str,
    file_types: List[Tuple[str, str]],
    is_save_mode: bool = False,
    default_extension: str = "",
    initial_dir: Path = DEFAULT_INITIAL_DIRECTORY,
) -> Optional[Path]:
    """
    GUIダイアログを表示して、ファイルを選択（または保存指定）させる。

    Args:
        title_message (str): ダイアログのタイトルメッセージ
        file_types (List[Tuple[str, str]]): フィルタリングするファイル形式のリスト
        is_save_mode (bool): 保存モード（新規ファイル名入力）にするかどうかのフラグ
        default_extension (str): 保存時のデフォルト拡張子（例: ".html"）
        initial_dir (Path): 初期表示ディレクトリ

    Returns:
        Optional[Path]: 選択されたファイルのパス（キャンセルの場合はNone）
    """
    # ── [ステップ1] ウィンドウの準備 ──
    root_window = tk.Tk()
    root_window.withdraw()
    root_window.attributes("-topmost", True)

    # ── [ステップ2] モード判定（保存指定かファイル開く指定か） ──
    if is_save_mode:
        selected_path_str = filedialog.asksaveasfilename(
            title=title_message,
            filetypes=file_types,
            defaultextension=default_extension,
            initialdir=str(initial_dir),
        )
    else:
        selected_path_str = filedialog.askopenfilename(
            title=title_message,
            filetypes=file_types,
            initialdir=str(initial_dir),
        )

    # ── [ステップ3] リソースの解放とパスオブジェクトの返却 ──
    root_window.destroy()

    if not selected_path_str:
        return None

    return Path(selected_path_str)


def get_image_exif_date(image_path: Path) -> Tuple[str, Optional[datetime]]:
    """
    画像ファイルのExifメタデータから撮影日時を取得し、表示用文字列とソート用日時オブジェクトを返す。

    Args:
        image_path (Path): 解析対象の画像ファイルパス

    Returns:
        Tuple[str, Optional[datetime]]: (表示用日時文字列, ソート用datetimeオブジェクト)
    """
    try:
        # ── [ステップ1] 画像ファイルのオープンとExif情報の取得 ──
        with Image.open(image_path) as target_image:
            # Pillowの公開APIである getexif() を使用（Pylanceの型解析に完全対応）
            exif_raw = target_image.getexif()
            if not exif_raw:
                return "", None

            # ── [ステップ2] ExifタグIDを読みやすい名称に変換 ──
            exif_data = {
                ExifTags.TAGS.get(key, key): value
                for key, value in exif_raw.items()
            }

            # ── [ステップ3] 撮影日時の抽出 ──
            # 36867 = DateTimeOriginal, 306 = DateTime
            date_str = (
                exif_data.get("DateTimeOriginal")
                or exif_data.get("DateTime")
                or exif_raw.get(36867)
                or exif_raw.get(306)
                or ""
            )
            if not date_str:
                return "", None

            # ── [ステップ4] 日時文字列の解析とフォーマット変換 ──
            parsed_datetime: Optional[datetime] = None
            try:
                parsed_datetime = datetime.strptime(
                    str(date_str), "%Y:%m:%d %H:%M:%S"
                )
                formatted_date = parsed_datetime.strftime("%Y/%m/%d %H:%M:%S")
                return formatted_date, parsed_datetime
            except ValueError:
                parts = str(date_str).split(" ")
                if len(parts) == 2:
                    formatted_date = f"{parts[0].replace(':', '/')} {parts[1]}"
                    return formatted_date, None
                return str(date_str), None

    except Exception:
        return "", None


def parse_html_table(html_file_path: Path) -> Dict[str, Dict[str, str]]:
    """
    既存のサムネイルHTMLテーブルを解析し、サムネイル画像相対パスをキーとしたデータ辞書を抽出する。

    Args:
        html_file_path (Path): 読み込むHTMLファイルのパス

    Returns:
        Dict[str, Dict[str, str]]: サムネイル相対パスをキーとした既存情報辞書
    """
    parsed_data: Dict[str, Dict[str, str]] = {}

    # ── [ステップ1] ファイル存在確認 ──
    if not html_file_path.exists():
        return parsed_data

    # ── [ステップ2] HTMLドキュメントの読み込みと構文解析 ──
    with open(html_file_path, "r", encoding="utf-8") as file_stream:
        soup_obj = BeautifulSoup(file_stream.read(), "html.parser")

    # ── [ステップ3] テーブル行（tr）の走査と列データの抽出 ──
    table_rows = soup_obj.find_all("tr")
    for row in table_rows:
        columns = row.find_all(["td", "th"])

        # 新フォーマット（7列）: ディレクトリ名, ファイル名, サムネイル, 撮影日時, 撮影地, コメント, flag
        if len(columns) >= 7:
            img_anchor_tag = columns[2].find("a")
            img_tag = columns[2].find("img")
            if not img_tag or not img_tag.get("src"):
                continue

            thumb_src = str(img_tag["src"])
            original_src = (
                str(img_anchor_tag["href"]) if img_anchor_tag else ""
            )

            parsed_data[thumb_src] = {
                "dir_name": columns[0].get_text(strip=True),
                "file_stem": columns[1].get_text(strip=True),
                "original_src": original_src,
                "exif_date": columns[3].get_text(strip=True),
                "location": columns[4].get_text(strip=True),
                "comment": columns[5].get_text(strip=True),
                "flag": columns[6].get_text(strip=True),
            }
        elif len(columns) >= 5:
            # 従来フォーマット対応
            img_tag = columns[1].find("img")
            if not img_tag or not img_tag.get("src"):
                continue

            thumb_src = str(img_tag["src"])
            parsed_data[thumb_src] = {
                "dir_name": "",
                "file_stem": columns[0].get_text(strip=True),
                "original_src": "",
                "exif_date": columns[2].get_text(strip=True),
                "location": columns[3].get_text(strip=True),
                "comment": columns[4].get_text(strip=True),
                "flag": "0",
            }

    print(
        f"既存ファイル {html_file_path.name} を読み込みました。データ行数: {len(parsed_data)}行"
    )

    return parsed_data


def generate_resized_thumbnail(
    source_image_path: Path,
    destination_image_path: Path,
    target_long_edge: int,
    overwrite_existing: bool = DEFAULT_OVERWRITE_THUMBNAIL,
) -> Tuple[int, int, bool]:
    """
    長辺の長さを基準としてアスペクト比を維持しながらサムネイル画像をリサイズ作成する。
    すでに存在し長辺pxが一致する場合は画像生成をスキップして既存のサイズを読み取って返す。

    Args:
        source_image_path (Path): 変換元画像のパス
        destination_image_path (Path): サムネイル画像の保存先パス
        target_long_edge (int): リサイズ後の長辺ピクセル数
        overwrite_existing (bool): すでに存在する場合に強制上書きするかどうか

    Returns:
        Tuple[int, int, bool]: (幅, 高さ, 新規にサムネイルファイルを生成したかどうかのフラグ)
    """
    # ── [ステップ1] 出力先フォルダの自動生成 ──
    destination_image_path.parent.mkdir(parents=True, exist_ok=True)

    # ── [ステップ2] 強制上書きフラグOFF時の既存ファイルチェック ──
    if not overwrite_existing and destination_image_path.exists():
        try:
            with Image.open(destination_image_path) as existing_thumb:
                existing_width, existing_height = existing_thumb.size
                existing_long_edge = max(existing_width, existing_height)

                # 既存サムネイルの長辺ピクセル数が指定値と一致している場合は生成をスキップ
                if existing_long_edge == target_long_edge:
                    return existing_width, existing_height, False
        except Exception:
            # 既存ファイルが破損している場合は再生成処理へ落とす
            pass

    try:
        # ── [ステップ3] 画像の読み込みと回転補正（Exif Orientation適用） ──
        with Image.open(source_image_path) as source_image:
            oriented_image = ImageOps.exif_transpose(source_image)
            original_width, original_height = oriented_image.size

            # ── [ステップ4] 長辺基準のリサイズ幅・高さの算出 ──
            if original_width >= original_height:
                target_width = target_long_edge
                target_height = int(
                    original_height * (target_long_edge / float(original_width))
                )
            else:
                target_height = target_long_edge
                target_width = int(
                    original_width * (target_long_edge / float(original_height))
                )

            # ── [ステップ5] 高品質リサイズ処理の実行 ──
            resized_image = oriented_image.resize(
                (target_width, target_height), Image.Resampling.LANCZOS
            )

            # ── [ステップ6] カラーモード調整とJPEG形式保存 ──
            if resized_image.mode in ("RGBA", "P"):
                resized_image = resized_image.convert("RGB")

            resized_image.save(destination_image_path, "JPEG", quality=85)

            return target_width, target_height, True

    except Exception as error_msg:
        print(
            f"警告: サムネイル生成中にエラーが発生しました ({source_image_path.name}): {error_msg}"
        )
        return target_long_edge, target_long_edge, False


def sort_image_records(
    records_list: List[Dict[str, Any]], sort_choice: str
) -> List[Dict[str, Any]]:
    """
    指定されたソート基準に従って画像レコードのリストを並び替える。

    Args:
        records_list (List[Dict[str, Any]]): ソート対象のレコードリスト
        sort_choice (str): ユーザーが選択したソートオプション ("1", "2", "3", "4")

    Returns:
        List[Dict[str, Any]]: 並び替え後のレコードリスト
    """
    # ── [ステップ1] ソート条件分岐処理 ──
    if sort_choice == "1":
        # 1: ファイル名順（A...Z）
        return sorted(
            records_list, key=lambda record: record["file_stem"].lower()
        )
    elif sort_choice == "2":
        # 2: ファイル名順（Z...A）
        return sorted(
            records_list,
            key=lambda record: record["file_stem"].lower(),
            reverse=True,
        )
    elif sort_choice == "4":
        # 4: Exifタイムスタンプ順（未来->過去）
        return sorted(
            records_list,
            key=lambda record: record["parsed_datetime"] or datetime.min,
            reverse=True,
        )
    else:
        # 3: Exifタイムスタンプ順（過去->未来）［デフォルト］
        return sorted(
            records_list,
            key=lambda record: record["parsed_datetime"] or datetime.min,
        )


def ask_yes_no_question(prompt_message: str, default_yes: bool = True) -> bool:
    """
    ユーザーに対して[y/n]形式の質問を行い、ブール値を返す。

    Args:
        prompt_message (str): 表示する質問メッセージ
        default_yes (bool): デフォルト値をYesにするかどうかのフラグ

    Returns:
        bool: ユーザーがYesを選択した場合True, Noを選択した場合False
    """
    default_str = "Y/n" if default_yes else "y/N"
    input_str = input(f"{prompt_message} [{default_str}]: ").strip().lower()

    if not input_str:
        return default_yes

    return input_str.startswith("y")


def generate_html_skeleton(
    table_editor_js_path: str = DEFAULT_TABLE_EDITOR_JS_PATH,
) -> List[str]:
    """
    HTMLドキュメントのヘッダーからテーブルヘッダー部分までのHTML文字列リストを生成する。

    Args:
        table_editor_js_path (str): 読み込むJavaScriptファイルの相対パスまたはURL

    Returns:
        List[str]: HTMLヘッダー部分の行文字列リスト
    """
    return [
        "<!DOCTYPE html>",
        '<html lang="ja">',
        "<head>",
        '  <meta charset="UTF-8">',
        "  <title>サムネイル一覧</title>",
        "  <style>",
        "    body { font-size: 14px; }",
        "    table { border-collapse: collapse; width: 100%; }",
        "    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }",
        "    th { background-color: #f2f2f2; }",
        "    img { display: block; height: auto; }",
        "  </style>",
        "  <!-- 外部エディタ用JSスクリプトを読み込み -->",
        f'  <script src="{table_editor_js_path}" defer></script>',
        "</head>",
        "<body>",
        "<!-- 操作用ボタンの設置エリア -->",
        '  <div style="margin-bottom: 15px;">',
        '    <button id="start_edit_button" onclick="switchToEditMode()">編集</button>',
        '    <div id="editor_controls" style="display: none;">',
        '      <button onclick="saveAndDownloadHtml()">保存 (HTML更新)</button>',
        "    </div>",
        "  </div>",
        "",
        "  <!-- Tabulator 描画用の空コンテナ -->",
        '  <div id="editor_container"></div>',
        "  <table>",
        "    <tr>",
        "      <th>ディレクトリ</th>",
        "      <th>ファイル名</th>",
        "      <th>サムネイル画像</th>",
        "      <th>撮影日時</th>",
        "      <th>撮影地</th>",
        "      <th>コメント</th>",
        "      <th>flag</th>",
        "    </tr>",
    ]


def get_subdir_by_cli(base_dir: Path) -> str:
    """base_directory内のサブディレクトリ一覧を表示し、ユーザーに番号選択させる"""
    # サブディレクトリの一覧を取得（アルファベット順）
    sub_dirs = sorted([p.name for p in base_dir.iterdir() if p.is_dir()])
    
    # 0番用のラベル表示と、実際のフォルダ名リストを保持
    display_options = [f"{base_dir.name} (基準ディレクトリ自身)"] + sub_dirs
    raw_options = [""] + sub_dirs  # 0番に対応する戻り値を空文字列とする
    
    print("\n--- 対象ディレクトリを選択してください ---")
    for idx, label in enumerate(display_options):
        print(f"{idx}: {label}")
    print("------------------------------------------")
    
    while True:
        choice = input(f"番号を入力してください (0-{len(display_options)-1}): ").strip()
        if choice.isdigit():
            val = int(choice)
            if 0 <= val < len(display_options):
                # 0の場合は ""、それ以外はフォルダ名を返す
                return raw_options[val]
        print("無効な入力です。リストの番号を入力してください。")

def process_generate_thumbnail_html() -> None:
    """
    【機能1】指定フォルダ内のJPG画像を検索し、画像ディレクトリ下にサムネイルを作成してHTMLを生成・更新する。
    """
    print("\n--- 1) サムネイルHTMLファイルの作成 ---")

    # ── [ステップ1] 基準ディレクトリの選択 ──
    print("対話ダイアログで基準ディレクトリを選択してください...")
    base_directory = select_directory_via_dialog(
        "基準ディレクトリを選択してください",
        initial_dir=DEFAULT_INITIAL_DIRECTORY,
    )
    if not base_directory:
        print("処理がキャンセルされました。")
        return

    # ── [ステップ2] サブディレクトリおよびパラメータの設定 ──
    sub_dir_input = get_subdir_by_cli(base_directory)
    # sub_dir_input = (
    #     input(
    #         "jpgファイルが存在する1段階下のディレクトリ名を入力してください（直下の場合は何も入力せずEnter）: "
    #     )
    #     .strip()
    # )

    if sub_dir_input:
        target_directory = base_directory / sub_dir_input
    else:
        target_directory = base_directory

    if not target_directory.exists():
        print(
            f"エラー: 指定されたディレクトリが見つかりません: {target_directory}"
        )
        return

    thumb_dir_name = (
        input(
            f"サムネイル画像を保存するサブディレクトリ名を入力してください [既定値: {DEFAULT_THUMBNAIL_DIRECTORY_NAME}]: "
        ).strip()
        or DEFAULT_THUMBNAIL_DIRECTORY_NAME
    )

    long_edge_input = input(
        f"サムネイル画像の長辺サイズ(px)を入力してください [既定値: {DEFAULT_THUMBNAIL_LONG_EDGE_PX}]: "
    ).strip()
    try:
        thumbnail_long_edge = (
            int(long_edge_input)
            if long_edge_input
            else DEFAULT_THUMBNAIL_LONG_EDGE_PX
        )
    except ValueError:
        print(
            f"数値が無効なため、既定値 {DEFAULT_THUMBNAIL_LONG_EDGE_PX}px を使用します。"
        )
        thumbnail_long_edge = DEFAULT_THUMBNAIL_LONG_EDGE_PX

    # ── [ステップ2.5] 処理制御オプションの追加問い合わせ ──
    should_update_exif = ask_yes_no_question(
        "JPGファイルのExifデータを再読み込みして撮影日時を更新しますか？",
        default_yes=DEFAULT_UPDATE_EXIF_DATE,
    )

    should_overwrite_thumb = ask_yes_no_question(
        "すでにサムネイル画像が存在する場合、強制的に上書き生成しますか？",
        default_yes=DEFAULT_OVERWRITE_THUMBNAIL,
    )

    # ── [ステップ3] HTML行のソート順選択 ──
    print("\nHTMLの行のソート順を選択してください:")
    print("  1: ファイル名順（A...Z）")
    print("  2: ファイル名順（Z...A）")
    print("  3: Exifタイムスタンプ順（過去->未来） [デフォルト]")
    print("  4: Exifタイムスタンプ順（未来->過去）")
    sort_choice_input = input("選択肢を入力してください (1-4) [既定値: 3]: ").strip()
    if sort_choice_input not in ["1", "2", "3", "4"]:
        sort_choice_input = "3"

    # ── [ステップ4] 出力先HTMLファイルの選択 ──
    print("出力するHTMLファイルのパスとファイル名をダイアログで指定してください...")
    output_html_path = select_file_via_dialog(
        title_message="保存するHTMLファイル名を指定してください",
        file_types=[("HTML File", "*.html"), ("All Files", "*.*")],
        is_save_mode=True,
        default_extension=".html",
        initial_dir=base_directory,
    )

    if not output_html_path:
        print("HTMLファイルの指定がキャンセルされたため処理を中止します。")
        return

    # ── [ステップ5] 既存HTMLファイルの解析（既存データの保持用） ──
    existing_data = parse_html_table(output_html_path)

    # ── [ステップ6] 対象JPGファイルの検出 ──
    jpg_files = sorted(
        [
            file_item
            for file_item in target_directory.iterdir()
            if file_item.is_file()
            and file_item.suffix.lower() in [".jpg", ".jpeg"]
        ]
    )

    if not jpg_files:
        print(
            f"対象ディレクトリにJPGファイルが見つかりませんでした: {target_directory}"
        )
        return

    print(f"{len(jpg_files)} 件のJPGファイルを処理中.", end="")

    # ── [ステップ7] サムネイル生成とデータ収集 ──
    thumbnails_save_dir = target_directory / thumb_dir_name
    image_dir_name = target_directory.name

    record_items: List[Dict[str, Union[str, Optional[datetime]]]] = []
    processed_thumb_paths: set = set()  # 実体ファイルが存在したパスの記録
    migrated_count = 0
    added_count = 0
    created_thumbnail_count = 0  # 実際に生成したサムネイル画像の件数

    for source_jpg_path in jpg_files:
        original_file_name = source_jpg_path.name
        file_stem = source_jpg_path.stem

        resized_thumb_path = thumbnails_save_dir / original_file_name

        # 長辺指定でサムネイルをリサイズ生成（長辺サイズチェック・作成フラグを含む）
        thumb_w, thumb_h, is_created = generate_resized_thumbnail(
            source_image_path=source_jpg_path,
            destination_image_path=resized_thumb_path,
            target_long_edge=thumbnail_long_edge,
            overwrite_existing=should_overwrite_thumb,
        )

        if is_created:
            created_thumbnail_count += 1

        relative_original_path = source_jpg_path.relative_to(
            base_directory
        ).as_posix()
        relative_thumb_path = resized_thumb_path.relative_to(
            base_directory
        ).as_posix()

        # 処理済みとしてパスを記録
        processed_thumb_paths.add(relative_thumb_path)

        # 既存データの引き継ぎチェック（サムネイルパスキー）
        is_existing_record = relative_thumb_path in existing_data

        if is_existing_record:
            location = existing_data[relative_thumb_path]["location"]
            comment = existing_data[relative_thumb_path]["comment"]
            flag = existing_data[relative_thumb_path].get("flag", "0")
            migrated_count += 1
        else:
            location = ""
            comment = ""
            flag = "0"
            added_count += 1

        # Exif日時の取得および引き継ぎ制御
        if should_update_exif or not is_existing_record:
            exif_date, parsed_datetime = get_image_exif_date(source_jpg_path)
        else:
            # Exifデータ更新を行わず既存値を維持する場合
            exif_date = existing_data[relative_thumb_path]["exif_date"]
            parsed_datetime = None
            if exif_date:
                try:
                    parsed_datetime = datetime.strptime(
                        exif_date, "%Y/%m/%d %H:%M:%S"
                    )
                except ValueError:
                    parsed_datetime = None

        record_items.append(
            {
                "image_dir_name": image_dir_name,
                "file_stem": file_stem,
                "original_file_name": original_file_name,
                "relative_original_path": relative_original_path,
                "relative_thumb_path": relative_thumb_path,
                "thumb_w": str(thumb_w),
                "thumb_h": str(thumb_h),
                "exif_date": exif_date,
                "parsed_datetime": parsed_datetime,
                "location": location,
                "comment": comment,
                "flag": flag,
            }
        )

        # 処理中の ... 表示
        if (added_count + migrated_count) % 10 == 0:
            print(".", end="")

    print("\n")

    # ── [ステップ7.5] 既存データのうち元JPGが存在しない「削除データ」の保持処理 ──
    deleted_count = 0
    for thumb_path, old_item in existing_data.items():
        if thumb_path not in processed_thumb_paths:
            # 既に [削除] が付いていなければ追加
            stem = old_item["file_stem"]
            if not stem.endswith("[削除]"):
                stem = f"{stem}[削除]"

            # Exif日時のパース（ソート用）
            parsed_dt: Optional[datetime] = None
            if old_item["exif_date"]:
                try:
                    parsed_dt = datetime.strptime(
                        old_item["exif_date"], "%Y/%m/%d %H:%M:%S"
                    )
                except ValueError:
                    parsed_dt = None

            record_items.append(
                {
                    "image_dir_name": old_item["dir_name"],
                    "file_stem": stem,
                    "original_file_name": Path(old_item["original_src"]).name,
                    "relative_original_path": old_item["original_src"],
                    "relative_thumb_path": thumb_path,
                    "thumb_w": str(DEFAULT_THUMBNAIL_LONG_EDGE_PX),
                    "thumb_h": str(DEFAULT_THUMBNAIL_LONG_EDGE_PX),
                    "exif_date": old_item["exif_date"],
                    "parsed_datetime": parsed_dt,
                    "location": old_item["location"],
                    "comment": old_item["comment"],
                    "flag": old_item["flag"],
                }
            )
            deleted_count += 1

    # ── [ステップ8] レコードのソート処理 ──
    sorted_records = sort_image_records(record_items, sort_choice_input)

    # ── [ステップ9] HTML行の構築 ──
    html_table_rows: List[str] = []
    for item in sorted_records:
        row_str = (
            f"    <tr>\n"
            f"      <td>{item['image_dir_name']}</td>\n"
            f"      <td>{item['file_stem']}</td>\n"
            f'      <td><a href="{item["relative_original_path"]}"><img src="{item["relative_thumb_path"]}" alt="{item["original_file_name"]}" title="{item["original_file_name"]}" width="{item["thumb_w"]}" height="{item["thumb_h"]}"></a></td>\n'
            f"      <td>{item['exif_date']}</td>\n"
            f"      <td>{item['location']}</td>\n"
            f"      <td>{item['comment']}</td>\n"
            f"      <td>{item['flag']}</td>\n"
            f"    </tr>"
        )
        html_table_rows.append(row_str)

    # ── [ステップ10] ログ出力とHTMLファイルの全体構築 ──
    total_output_rows = len(html_table_rows)
    print(f"サムネイル画像作成 {created_thumbnail_count}件")
    print(
        f"JPGファイル {len(jpg_files)} 個確認。出力総行数: {total_output_rows}行 "
        f"（既存移行: {migrated_count}行, 新規追加: {added_count}行, 削除データ保持: {deleted_count}行）"
    )

    full_html_content = generate_html_skeleton(DEFAULT_TABLE_EDITOR_JS_PATH)
    full_html_content.extend(html_table_rows)
    full_html_content.extend(["  </table>", "</body>", "</html>"])

    # ── [ステップ11] ファイルへの書き込み実行（上書き前バックアップ実施） ──
    create_backup_file(output_html_path)

    with open(output_html_path, "w", encoding="utf-8") as file_writer:
        file_writer.write("\n".join(full_html_content))

    print(f"成功: サムネイルHTMLファイルを作成・更新しました -> {output_html_path}")


def process_convert_html_to_csv() -> None:
    """
    【機能2】指定したサムネイルHTMLファイルを読み込み、指定フォーマットのCSVファイルとして書き出す。
    """
    print("\n--- 2) サムネイルHTMLファイルをCSVファイルに変換 ---")

    # ── [ステップ1] 変換元HTMLファイルの選択 ──
    print("変換元のHTMLファイルをダイアログで選択してください...")
    input_html_path = select_file_via_dialog(
        title_message="変換対象のHTMLファイルを選択してください",
        file_types=[("HTML File", "*.html"), ("All Files", "*.*")],
        is_save_mode=False,
        initial_dir=DEFAULT_INITIAL_DIRECTORY,
    )

    if not input_html_path or not input_html_path.exists():
        print("有効なファイルが選択されませんでした。処理を中止します。")
        return

    # ── [ステップ2] 保存先CSVファイルの選択 ──
    print("保存先のCSVファイルパスをダイアログで指定してください...")
    output_csv_path = select_file_via_dialog(
        title_message="保存するCSVファイル名を指定してください",
        file_types=[("CSV File", "*.csv"), ("All Files", "*.*")],
        is_save_mode=True,
        default_extension=".csv",
        initial_dir=input_html_path.parent,
    )

    if not output_csv_path:
        print("保存先の指定がキャンセルされました。")
        return

    # ── [ステップ3] HTMLの解析とデータ抽出 ──
    parsed_data = parse_html_table(input_html_path)
    total_data_rows = len(parsed_data)

    print(f"HTMLデータ行数 {total_data_rows}行 をCSV出力用に抽出しました。")

    # ── [ステップ4] CSVファイルへの構造化書き込み（上書き前バックアップ実施） ──
    create_backup_file(output_csv_path)

    with open(
        output_csv_path, "w", encoding="utf-8-sig", newline=""
    ) as csv_file_stream:
        csv_writer = csv.writer(csv_file_stream)

        # ヘッダー行の書き込み
        csv_writer.writerow(
            [
                "画像相対パス",
                "サムネイル画像相対パス",
                "Exif日時",
                "撮影地",
                "コメント",
                "flag",
            ]
        )

        # データ行の書き込み
        for thumb_src, item_data in parsed_data.items():
            csv_writer.writerow(
                [
                    item_data["original_src"],
                    thumb_src,
                    item_data["exif_date"],
                    item_data["location"],
                    item_data["comment"],
                    item_data["flag"],
                ]
            )

    print(
        f"成功: CSVファイルへの変換が完了しました（出力件数: {total_data_rows}件） -> {output_csv_path}"
    )


def process_convert_csv_to_html() -> None:
    """
    【機能3】指定したCSVファイルを読み込み、指定フォーマットのサムネイルHTMLファイルに復元・出力する。
    サムネイル画像の自動生成・リサイズを行い、imgタグにwidth/height属性を設定する。
    """
    print("\n--- 3) CSVファイルをサムネイルHTMLファイルに変換 ---")

    # ── [ステップ1] 変換元CSVファイルの選択 ──
    print("変換元のCSVファイルをダイアログで選択してください...")
    input_csv_path = select_file_via_dialog(
        title_message="変換対象のCSVファイルを選択してください",
        file_types=[("CSV File", "*.csv"), ("All Files", "*.*")],
        is_save_mode=False,
        initial_dir=DEFAULT_INITIAL_DIRECTORY,
    )

    if not input_csv_path or not input_csv_path.exists():
        print("有効なCSVファイルが選択されませんでした。処理を中止します。")
        return

    # ── [ステップ2] 出力先HTMLファイルの選択 ──
    print("保存先のHTMLファイルパスをダイアログで指定してください...")
    output_html_path = select_file_via_dialog(
        title_message="保存するHTMLファイル名を指定してください",
        file_types=[("HTML File", "*.html"), ("All Files", "*.*")],
        is_save_mode=True,
        default_extension=".html",
        initial_dir=input_csv_path.parent,
    )

    if not output_html_path:
        print("保存先の指定がキャンセルされました。")
        return

    # ── [ステップ2.5] サムネイル生成パラメータおよび対話問い合わせ ──
    long_edge_input = input(
        f"サムネイル画像の長辺サイズ(px)を入力してください [既定値: {DEFAULT_THUMBNAIL_LONG_EDGE_PX}]: "
    ).strip()
    try:
        thumbnail_long_edge = (
            int(long_edge_input)
            if long_edge_input
            else DEFAULT_THUMBNAIL_LONG_EDGE_PX
        )
    except ValueError:
        print(
            f"数値が無効なため、既定値 {DEFAULT_THUMBNAIL_LONG_EDGE_PX}px を使用します。"
        )
        thumbnail_long_edge = DEFAULT_THUMBNAIL_LONG_EDGE_PX

    should_update_exif = ask_yes_no_question(
        "実体JPGファイルのExifデータを再読み込みして撮影日時を更新しますか？",
        default_yes=DEFAULT_UPDATE_EXIF_DATE,
    )

    should_overwrite_thumb = ask_yes_no_question(
        "すでにサムネイル画像が存在する場合、強制的に上書き生成しますか？",
        default_yes=DEFAULT_OVERWRITE_THUMBNAIL,
    )

    # ── [ステップ3] CSVデータのパース読み込み ──
    csv_rows_data: List[Tuple[str, str, str, str, str, str]] = []

    with open(
        input_csv_path, "r", encoding="utf-8-sig", errors="ignore"
    ) as csv_file_stream:
        csv_reader = csv.reader(csv_file_stream)
        # ヘッダー行をスキップ
        next(csv_reader, None)

        for data_row in csv_reader:
            if len(data_row) >= 6:
                csv_rows_data.append(
                    (
                        data_row[0],  # 画像相対パス
                        data_row[1],  # サムネイル画像相対パス
                        data_row[2],  # Exif日時
                        data_row[3],  # 撮影地
                        data_row[4],  # コメント
                        data_row[5],  # flag
                    )
                )

    total_csv_rows = len(csv_rows_data)
    print(f"{total_csv_rows} 件のCSVデータを処理中...")

    # ── [ステップ4] HTML文書構造の構築 ──
    html_lines: List[str] = generate_html_skeleton(DEFAULT_TABLE_EDITOR_JS_PATH)

    # ── [ステップ5] サムネイル生成・Exif再読み込み・HTMLタグ構築 ──
    base_dir_path = output_html_path.parent
    created_thumbnail_count = 0

    for original_src, thumb_src, exif_date, location, comment, flag in csv_rows_data:
        actual_original_path = base_dir_path / original_src
        actual_thumb_path = base_dir_path / thumb_src

        original_path = Path(original_src)
        image_dir_name = original_path.parent.name
        file_stem = original_path.stem
        original_file_name = original_path.name

        # サムネイル画像の存在確認およびリサイズ生成処理
        thumb_w, thumb_h = DEFAULT_THUMBNAIL_LONG_EDGE_PX, DEFAULT_THUMBNAIL_LONG_EDGE_PX
        if actual_original_path.exists():
            thumb_w, thumb_h, is_created = generate_resized_thumbnail(
                source_image_path=actual_original_path,
                destination_image_path=actual_thumb_path,
                target_long_edge=thumbnail_long_edge,
                overwrite_existing=should_overwrite_thumb,
            )
            if is_created:
                created_thumbnail_count += 1
        elif actual_thumb_path.exists():
            # 原本が無いがサムネイルが存在する場合は既存ファイルからサイズを取得
            try:
                with Image.open(actual_thumb_path) as existing_thumb:
                    thumb_w, thumb_h = existing_thumb.size
            except Exception:
                pass

        # Exifデータの更新オプションが有効な場合、実体ファイルが存在すれば読み取る
        target_exif_date = exif_date
        if should_update_exif and actual_original_path.exists():
            extracted_date, _ = get_image_exif_date(actual_original_path)
            if extracted_date:
                target_exif_date = extracted_date

        row_str = (
            f"    <tr>\n"
            f"      <td>{image_dir_name}</td>\n"
            f"      <td>{file_stem}</td>\n"
            f'      <td><a href="{original_src}"><img src="{thumb_src}" alt="{original_file_name}" title="{original_file_name}" width="{thumb_w}" height="{thumb_h}"></a></td>\n'
            f"      <td>{target_exif_date}</td>\n"
            f"      <td>{location}</td>\n"
            f"      <td>{comment}</td>\n"
            f"      <td>{flag}</td>\n"
            f"    </tr>"
        )
        html_lines.append(row_str)

    html_lines.extend(["  </table>", "</body>", "</html>"])

    # ── [ステップ6] メッセージ出力とHTMLファイルの書き出し（バックアップ実施） ──
    print(f"サムネイル画像作成 {created_thumbnail_count}件")
    print(f"CSVレコード {total_csv_rows} 個確認。出力総行数: {total_csv_rows}行")

    create_backup_file(output_html_path)

    with open(output_html_path, "w", encoding="utf-8") as html_file_writer:
        html_file_writer.write("\n".join(html_lines))

    print(
        f"成功: HTMLファイルへの変換が完了しました（出力件数: {total_csv_rows}件） -> {output_html_path}"
    )

def main_interactive_menu() -> None:
    """
    ユーザー対話用のコンソールメニューを表示し、選択に応じて処理分岐を行う。
    """
    print("==================================================")
    print(" 処理内容を選択してください")
    print(
        " １） 指定ディレクトリの全jpgファイルを対象に、サムネイルHTMLファイルを作成する（既存更新含む）"
    )
    print(" ２） 指定したサムネイルHTMLファイルをCSVファイルに変換する")
    print(" ３） 指定したCSVファイルをサムネイルHTMLファイルに変換する")
    print("==================================================")

    # ── [ステップ1] ユーザー入力の受け取り ──
    user_choice = input("選択肢を入力してください (1, 2, 3): ").strip()

    # ── [ステップ2] 選択に応じた処理分岐の実行 ──
    if user_choice in ["1", "１"]:
        process_generate_thumbnail_html()
    elif user_choice in ["2", "２"]:
        process_convert_html_to_csv()
    elif user_choice in ["3", "３"]:
        process_convert_csv_to_html()
    else:
        print("エラー: 無効な選択肢が入力されました。プログラムを終了します。")


if __name__ == "__main__":
    main_interactive_menu()