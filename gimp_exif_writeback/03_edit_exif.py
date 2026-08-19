#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""JPEG画像内の既存Exifタグを安全に検索・インタラクティブに書き換えるスクリプト。

このモジュールは、指定されたJPEG画像に存在するExifデータ（IFD0、ExifIFD、GPSInfo）を
`02_dump_exif_all.py` を動的にロードして一覧表示し、ユーザーがコンソールから入力した
「タグ名」と「新しい値」に基づいて値を安全に更新・保存します。
入力値は `ast.literal_eval` で自動評価され、既存データの型と一致する場合のみ書き換えが実行されます。

Attributes:
    なし (コマンドライン引数より画像ファイルパスを受け取り、対話形式で操作します)

Requires:
    - Python 3.x
    - Pillow (PIL): 画像処理・Exifデータ編集用ライブラリ (pip install Pillow)
    - 02_dump_exif_all.py: 同一ディレクトリ内に配置されている必要のあるExifダンプ用スクリプト

Author:
    Google Gemini3.6 Flash Collaborating Coding

Version:
    1.0.0 (2026/08/15)
"""

import sys
import os
import ast
import importlib.util
from types import ModuleType
from typing import Optional, Tuple, Any
from PIL import Image, ExifTags

# ── [グローバル変数（設定項目）] ──
# 呼び出すExif復元スクリプトのファイル名
EXIF_DUMP_SCRIPT_NAME: str = "02_dump_exif_all.py"


def load_module_from_file(module_filename: str) -> ModuleType:
    """
    数字始まりなど通常の import 構文が使えない Python ファイルを動的に読み込みます。

    Args:
        module_filename (str): 同じディレクトリ内にある読み込み対象のファイル名（例: "02_dump_exif_all.py"）

    Returns:
        ModuleType: ロードされたモジュールオブジェクト
    """
    # ── [ステップ1] 対象ファイルのパス構築と存在確認 ──
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, module_filename)

    if not os.path.exists(file_path):
        print(f"エラー: {module_filename} が同じディレクトリに見つかりません。")
        sys.exit(1)

    # ── [ステップ2] モジュールスペックの取得と動的ロード ──
    module_name = os.path.splitext(module_filename)[0]
    module_spec = importlib.util.spec_from_file_location(module_name, file_path)

    if module_spec is None or module_spec.loader is None:
        print(f"エラー: {module_filename} の読み込みに失敗しました。")
        sys.exit(1)

    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)

    return loaded_module


# ── [外部モジュールの動的読み込み実行] ──
dump_exif_module = load_module_from_file(EXIF_DUMP_SCRIPT_NAME)

# モジュールから必要な関数を取り出してローカル変数に割り当て
print_all_exif_data = dump_exif_module.print_all_exif_data


def find_tag_id_and_ifd_from_image(
    image_path: str, tag_name_query: str
) -> Tuple[Optional[int], Optional[str]]:
    """
    対象画像ファイルの既存 Exif データを走査し、
    指定されたタグ名が『実際にどの IFD 領域に存在するか』を特定します。
    画像内に存在しないタグの場合は (None, None) を返します。

    Args:
        image_path (str): 対象画像ファイルのパス
        tag_name_query (str): 検索するタグ名（例: "DateTimeOriginal"）

    Returns:
        Tuple[Optional[int], Optional[str]]: (タグID, 存在するIFD種別)。存在しない場合は (None, None)
    """
    try:
        with Image.open(image_path) as current_image:
            exif_data = current_image.getexif()

            if not exif_data:
                return None, None

            # ── [ステップ1] IFD0 (メイン領域) の現物検索 ──
            for tag_id in exif_data.keys():
                if ExifTags.TAGS.get(tag_id) == tag_name_query:
                    return tag_id, "IFD0"

            # ── [ステップ2] ExifIFD (詳細サブ領域) の現物検索 ──
            try:
                exif_sub_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                if exif_sub_ifd:
                    for tag_id in exif_sub_ifd.keys():
                        if ExifTags.TAGS.get(tag_id) == tag_name_query:
                            return tag_id, "ExifIFD"
            except Exception:
                pass

            # ── [ステップ3] GPSInfo (位置情報領域) の現物検索 ──
            try:
                gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    for tag_id in gps_ifd.keys():
                        if ExifTags.GPSTAGS.get(tag_id) == tag_name_query:
                            return tag_id, "GPSInfo"
            except Exception:
                pass

    except Exception as error_message:
        print(f"エラー: 画像ファイルの解析中にエラーが発生しました -> {error_message}")

    # 現物画像内にタグが存在しなかった場合は None を返す
    return None, None


def parse_user_input(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    ユーザーのカンマ区切り入力を「タグ名」と「書き換え値の文字列」に分解・整形します。

    Args:
        user_input (str): コンソールからの入力文字列（例: "GPSLongitude, (145.0, 23.2, 30.0)"）

    Returns:
        Tuple[Optional[str], Optional[str]]: (タグ名, 値の文字列) のタプル。形式不正の場合は (None, None)
    """
    # ── [ステップ1] カンマ区切りの分解 ──
    if "," not in user_input:
        return None, None

    input_parts = user_input.split(",", 1)
    tag_name = input_parts[0].strip()
    raw_value_str = input_parts[1].strip()

    if not tag_name or not raw_value_str:
        return None, None

    return tag_name, raw_value_str


def convert_and_validate_value(raw_value_str: str, old_value: Any) -> Tuple[Any, bool]:
    """
    入力文字列を適切な Python オブジェクト（数値・タプル・リスト等）に変換し、
    既存の値 (old_value) と型が一致しているかを判定します。

    Args:
        raw_value_str (str): ユーザーが入力した値の文字列
        old_value (Any): 画像から取得した変更前の値

    Returns:
        Tuple[Any, bool]: (変換後の値, 型が一致しているかのフラグ)
    """
    # 入力文字列を Python の型 (tuple, list, int, float 等) として評価・変換を試みる
    try:
        parsed_value = ast.literal_eval(raw_value_str)
    except (ValueError, SyntaxError):
        parsed_value = raw_value_str

    old_type = type(old_value)
    parsed_type = type(parsed_value)

    # ── [型チェック] ──
    if old_type == parsed_type:
        return parsed_value, True

    # 既存値が int で入力が float の場合など、数値間の安全な変換の調整
    if old_type is float and isinstance(parsed_value, int):
        return float(parsed_value), True

    # 型が一致しない場合は不正として扱う
    return parsed_value, False


def update_exif_value(
    image_path: str, tag_name: str, raw_value_str: str, output_path: Optional[str] = None
) -> bool:
    """
    対象画像に『実際に存在する』Exif タグの値を特定し、型チェックを行ったうえで
    その IFD 領域の値を書き換えて保存します。

    Args:
        image_path (str): 対象画像ファイルのパス
        tag_name (str): 書き換えるタグ名
        raw_value_str (str): 新しく設定する値の文字列
        output_path (Optional[str]): 保存先パス（None の場合は元画像に上書き）

    Returns:
        bool: 成功時 True, 失敗時 False
    """
    # ── [ステップ1] 対象画像の現物データから ID と IFD 種別を検索 ──
    tag_id, ifd_type = find_tag_id_and_ifd_from_image(image_path, tag_name)

    # 現物内にタグが存在しない場合はエラーとして処理を中断する
    if tag_id is None or ifd_type is None:
        print(f"\nエラー: 指定されたタグ名 '{tag_name}' は、この画像ファイル内に存在しません。")
        print("新規タグの追加は行えません。一覧に表示されている既存のタグ名を指定してください。")
        return False

    save_target_path = output_path if output_path else image_path

    try:
        # ── [ステップ2] 画像の読み込みと既存値 (old_value) の取得 ──
        with Image.open(image_path) as current_image:
            exif_data = current_image.getexif()
            old_value: Any = None

            if ifd_type == "IFD0":
                old_value = exif_data.get(tag_id)
            elif ifd_type == "GPSInfo":
                gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                old_value = gps_ifd.get(tag_id)
            elif ifd_type == "ExifIFD":
                exif_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                old_value = exif_ifd.get(tag_id)

            # ── [ステップ3] 型判定と不一致エラー処理 ──
            converted_new_value, is_type_valid = convert_and_validate_value(
                raw_value_str, old_value
            )

            if not is_type_valid:
                print(f"\nエラー: 入力された値の型が既存データの型と一致しません。")
                print(f"  ・既存の値: {old_value} (型: {type(old_value).__name__})")
                print(f"  ・入力された値: {converted_new_value} (型: {type(converted_new_value).__name__})")
                print("書き込み処理を中断しました。")
                return False

            # ── [ステップ4] 変換された値の書き込み ──
            if ifd_type == "IFD0":
                exif_data[tag_id] = converted_new_value
            elif ifd_type == "GPSInfo":
                gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                gps_ifd[tag_id] = converted_new_value
            elif ifd_type == "ExifIFD":
                exif_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                exif_ifd[tag_id] = converted_new_value

            # ── [ステップ5] 更新後の画像の保存と実行結果表示 ──
            current_image.save(save_target_path, exif=exif_data)
            print(
                f"\n[成功] [{ifd_type}] '{tag_name}' (ID: {tag_id}) の値を "
                f"'{old_value}' から '{converted_new_value}' に書き換えました。"
            )
            print(f"保存先: {save_target_path}")
            return True

    except Exception as error_message:
        print(f"\nエラー: Exif の更新処理中にエラーが発生しました -> {error_message}")
        return False


def main() -> None:
    """
    メイン処理を実行します。
    引数チェック、Exif一覧表示、ユーザー入力受付け、書き換え処理を順番に行います。

    Returns:
        None
    """
    # ── [ステップ1] コマンドライン引数の確認 ──
    if len(sys.argv) < 2:
        print("使用方法: python 03_edit_exif.py <画像ファイルのパス>")
        sys.exit(1)

    target_image_path = sys.argv[1]

    if not os.path.exists(target_image_path):
        print(f"エラー: 指定されたファイルが存在しません -> {target_image_path}")
        sys.exit(1)

    # ── [ステップ2] 02_dump_exif_all.py を呼び出して一覧表示 ──
    print_all_exif_data(target_image_path)
    print("\n" + "=" * 80)

    # ── [ステップ3] コンソールからの対話入力 ──
    prompt_message = "書き換える タグ名, 値 をカンマ区切りで入力してください\n（例: GPSLongitude, (145.0, 23.2, 30.0)）\n> "
    user_input = input(prompt_message)

    tag_name, raw_value_str = parse_user_input(user_input)

    if not tag_name or not raw_value_str:
        print("エラー: 入力形式が正しくありません。「タグ名, 値」の形式で入力してください。")
        sys.exit(1)

    # ── [ステップ4] 現物ベースの判定・書き換え実行 ──
    update_exif_value(target_image_path, tag_name, raw_value_str)


if __name__ == "__main__":
    main()
