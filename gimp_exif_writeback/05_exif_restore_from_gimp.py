#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Gimp等の編集により上書き・改変されたExif情報（Software, DateTime）を判定・復元するスクリプト。

このモジュールは、指定されたJPEG画像の `Software` タグを解析し、Gimpによる書き換えの有無に応じて処理を自動分岐します。
オリジナル画像の場合は `Make` および `Model` をキーとして本来の `Software` タグ情報を JSON データベースに自動登録し、
Gimp書き換え画像の場合はデータベースを参照して本来の `Software` 値を復元（元々存在しない場合はタグを削除）するとともに、
`DateTime` タグを `DateTimeOriginal`（撮影日時）の値で復元して上書き保存します。

Attributes:
    JSON_DATABASE_DIRECTORY_PATH (str): JSON データベースファイルの保存先ディレクトリ（デフォルト: ~/）。
    JSON_DATABASE_FILE_NAME (str): データベースのファイル名（デフォルト: .exif_restore_from_gimp.json）。
    JSON_DATABASE_FULL_PATH (str): データベースファイルのフルパス。

Requires:
    - Python 3.x
    - Pillow (PIL): 画像処理・Exifデータ解析および編集用ライブラリ (pip install Pillow)

Author:
    Google Gemini Collaborative Coding

Version:
    1.0.0 (2026/08/16)
    1.1.0 (2026/08/21) キー重複時の Software 値変更検知・DB更新スキップ判定を追加
    1.2.0 (2026/08/23) 簡易表示モード (is_simple_mode) オプションの追加
    1.2.1 (2026/08/23) 簡易表示時の[Skip]/[Error]/[登録]表示判定ロジックの修正
"""

import json
import os
import sys
from typing import Dict, Optional, Tuple
from PIL import Image, ExifTags

# ── [グローバル変数（設定項目）] ──
# データベース JSON ファイルの出力先ディレクトリおよびファイル名
JSON_DATABASE_DIRECTORY_PATH: str = os.path.expanduser("~/")
JSON_DATABASE_FILE_NAME: str = ".exif_restore_from_gimp.json"

# JSON ファイルのフルパス構築
JSON_DATABASE_FULL_PATH: str = os.path.join(
    JSON_DATABASE_DIRECTORY_PATH, JSON_DATABASE_FILE_NAME
)


def load_json_database(database_file_path: str) -> Dict[str, Optional[str]]:
    """JSON データベースファイルを読み込みます。ファイルが存在しない場合は空の辞書を返します。

    Args:
        database_file_path (str): 読み込む JSON ファイルのフルパス

    Returns:
        Dict[str, Optional[str]]: 読み込まれたデータベース辞書（キー: "Make|Model", 値: Software文字列または None）
    """
    if not os.path.exists(database_file_path):
        return {}

    try:
        with open(database_file_path, "r", encoding="utf-8") as file_handle:
            database_data: Dict[str, Optional[str]] = json.load(file_handle)
            return database_data
    except Exception as error_message:
        print(f"警告: JSON データベースの読み込みに失敗しました -> {error_message}")
        return {}


def save_json_database(
    database_data: Dict[str, Optional[str]], database_file_path: str
) -> bool:
    """データベース辞書を JSON ファイルとして保存します。

    Args:
        database_data (Dict[str, Optional[str]]): 保存するデータベース辞書
        database_file_path (str): 保存先の JSON ファイルのフルパス

    Returns:
        bool: 保存成功時 True, 失敗時 False
    """
    try:
        directory_path = os.path.dirname(database_file_path)
        if directory_path and not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)

        with open(database_file_path, "w", encoding="utf-8") as file_handle:
            json.dump(database_data, file_handle, ensure_ascii=False, indent=4)
        return True
    except Exception as error_message:
        print(f"エラー: JSON データベースの保存に失敗しました -> {error_message}")
        return False


def find_tag_id_and_ifd_from_image(
    image_path: str, tag_name_query: str
) -> Tuple[Optional[int], Optional[str]]:
    """対象画像ファイルの既存 Exif データを走査し、指定されたタグ名が存在する タグID と IFD 領域を特定します。

    Args:
        image_path (str): 対象画像ファイルのパス
        tag_name_query (str): 検索するタグ名（例: "Software", "DateTimeOriginal"）

    Returns:
        Tuple[Optional[int], Optional[str]]: (タグID, 存在するIFD種別)。存在しない場合は (None, None)
    """
    try:
        with Image.open(image_path) as current_image:
            exif_data = current_image.getexif()
            if not exif_data:
                return None, None

            # ── [ステップ1] IFD0 (メイン領域) の検索 ──
            for tag_id, registered_name in ExifTags.TAGS.items():
                if registered_name == tag_name_query and tag_id in exif_data.keys():
                    return tag_id, "IFD0"

            # ── [ステップ2] ExifIFD (詳細サブ領域) の検索 ──
            try:
                exif_sub_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                if exif_sub_ifd:
                    for tag_id, registered_name in ExifTags.TAGS.items():
                        if (
                            registered_name == tag_name_query
                            and tag_id in exif_sub_ifd.keys()
                        ):
                            return tag_id, "ExifIFD"
            except Exception:
                pass

            # ── [ステップ3] GPSInfo (位置情報領域) の検索 ──
            try:
                gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    for tag_id, registered_name in ExifTags.GPSTAGS.items():
                        if (
                            registered_name == tag_name_query
                            and tag_id in gps_ifd.keys()
                        ):
                            return tag_id, "GPSInfo"
            except Exception:
                pass

    except Exception:
        pass

    return None, None


def get_exif_tag_value_by_name(image_path: str, tag_name: str) -> Optional[str]:
    """画像内から指定されたタグ名の値を文字列として安全に取得します。

    Args:
        image_path (str): 対象画像ファイルのパス
        tag_name (str): 取得したいタグ名

    Returns:
        Optional[str]: タグの値。取得できない場合は None
    """
    tag_id, ifd_type = find_tag_id_and_ifd_from_image(image_path, tag_name)
    if tag_id is None or ifd_type is None:
        return None

    try:
        with Image.open(image_path) as current_image:
            exif_data = current_image.getexif()

            if ifd_type == "IFD0":
                tag_value = exif_data.get(tag_id)
                return str(tag_value) if tag_value is not None else None

            elif ifd_type == "ExifIFD":
                exif_sub_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                tag_value = exif_sub_ifd.get(tag_id)
                return str(tag_value) if tag_value is not None else None

    except Exception:
        pass

    return None


def register_original_software_database(
    image_path: str, database_file_path: str, is_simple_mode: bool = False
) -> str:
    """Gimpで書き換えられていないオリジナルの JPG ファイルから「Make」「Model」「Software」を取得し、

    「Make|Model」をキーとして JSON データベースに登録・保存します。
    既にデータが存在する場合、Software 値が一致していれば更新をスキップし、異なる場合のみアップデートします。

    Args:
        image_path (str): オリジナル画像のファイルパス
        database_file_path (str): JSON データベースのファイルパス
        is_simple_mode (bool): 簡易表示モードフラグ（デフォルト: False）

    Returns:
        str: 処理結果ステータス ("REGISTERED", "UPDATED", "SKIPPED", "ERROR")
    """
    # ── [ステップ1] 各属性値の取得 ──
    make_value = get_exif_tag_value_by_name(image_path, "Make")
    model_value = get_exif_tag_value_by_name(image_path, "Model")
    raw_software_value = get_exif_tag_value_by_name(image_path, "Software")

    if not make_value or not model_value:
        if not is_simple_mode:
            print(
                "エラー: 画像内に Make または Model の情報が存在しません。DB登録をスキップします。"
            )
        return "ERROR"

    make_clean_value = make_value.strip()
    model_clean_value = model_value.strip()

    # Software タグの有無の判定（タグが無い、あるいは空文字の場合は None とする）
    software_clean_value: Optional[str] = (
        raw_software_value.strip() if raw_software_value is not None else None
    )

    # ── [ステップ2] JSON データベースとの照合・差異チェック ──
    database_data = load_json_database(database_file_path)
    database_key = f"{make_clean_value}|{model_clean_value}"

    is_update = False
    if database_key in database_data:
        existing_software_value = database_data[database_key]

        # 登録済みの値と新規の値が完全に一致する場合は処理を行わずスキップ
        if existing_software_value == software_clean_value:
            if not is_simple_mode:
                display_val = (
                    f"'{software_clean_value}'"
                    if software_clean_value
                    else "なし (null)"
                )
                print(f"[データベーススキップ]")
                print(f"  ・キー      : '{database_key}'")
                print(
                    f"  ・Software  : {display_val} (既存データと同一のため更新を行いません)"
                )
            return "SKIPPED"

        # 値が異なる場合はアップデート
        is_update = True
        if not is_simple_mode:
            old_val_disp = (
                f"'{existing_software_value}'"
                if existing_software_value
                else "なし (null)"
            )
            new_val_disp = (
                f"'{software_clean_value}'" if software_clean_value else "なし (null)"
            )
            print(f"[データベースアップデート]")
            print(f"  ・キー      : '{database_key}'")
            print(f"  ・Software  : {old_val_disp} -> {new_val_disp}")
    else:
        if not is_simple_mode:
            # 新規登録時のログ出力
            new_val_disp = (
                f"'{software_clean_value}'" if software_clean_value else "なし (null)"
            )
            print(f"[データベース新規登録]")
            print(f"  ・キー      : '{database_key}'")
            print(f"  ・Software  : {new_val_disp}")

    # ── [ステップ3] JSON データベースへ保存 ──
    database_data[database_key] = software_clean_value

    if save_json_database(database_data, database_file_path):
        if not is_simple_mode:
            print(f"  ・保存先    : {database_file_path}")
        return "UPDATED" if is_update else "REGISTERED"

    return "ERROR"


def restore_exif_data_from_gimp(
    image_path: str, database_file_path: str, is_simple_mode: bool = False
) -> bool:
    """Gimpで書き換えられた JPG ファイルの Exif（Software, DateTime）を復元して上書き保存します。

    ※ 元の Software が「なし (null)」の場合は Software タグ自体を削除します。

    Args:
        image_path (str): 復元対象の画像ファイルパス
        database_file_path (str): JSON データベースのファイルパス
        is_simple_mode (bool): 簡易表示モードフラグ（デフォルト: False）

    Returns:
        bool: 復元成功時 True, 失敗時 False
    """
    # ── [ステップ1] データベース照合用 Make/Model の取得 ──
    make_value = get_exif_tag_value_by_name(image_path, "Make")
    model_value = get_exif_tag_value_by_name(image_path, "Model")

    if not make_value or not model_value:
        if not is_simple_mode:
            print(
                "エラー: 復元に必要な Make または Model の情報が取得できませんでした。"
            )
        return False

    database_key = f"{make_value.strip()}|{model_value.strip()}"
    database_data = load_json_database(database_file_path)

    if database_key not in database_data:
        if not is_simple_mode:
            print(f"エラー: データベースにキー '{database_key}' が未登録です。")
            print(
                "先にこのカメラ（Make/Model）で撮影されたオリジナル画像を通してください。"
            )
        return False

    restored_software_value = database_data[database_key]

    # ── [ステップ2] DateTimeOriginal または DateTimeDigitized の日時取得 ──
    original_date_time_value = get_exif_tag_value_by_name(
        image_path, "DateTimeOriginal"
    )
    if not original_date_time_value:
        original_date_time_value = get_exif_tag_value_by_name(
            image_path, "DateTimeDigitized"
        )

    if not original_date_time_value:
        if not is_simple_mode:
            print(
                "エラー: DateTimeOriginal および DateTimeDigitized を取得できませんでした。"
            )
        return False

    # ── [ステップ3] タグ ID の特定と書き換え・削除処理 ──
    software_tag_id, _ = find_tag_id_and_ifd_from_image(image_path, "Software")
    date_time_tag_id, _ = find_tag_id_and_ifd_from_image(image_path, "DateTime")

    # 万が一 IFD0 に DateTime タグが無い場合は ExifTags から基本 ID (0x0132) を取得
    if date_time_tag_id is None:
        for tag_id, registered_name in ExifTags.TAGS.items():
            if registered_name == "DateTime":
                date_time_tag_id = tag_id
                break

    if date_time_tag_id is None:
        if not is_simple_mode:
            print("エラー: DateTime タグ ID の特定に失敗しました。")
        return False

    try:
        with Image.open(image_path) as current_image:
            exif_data = current_image.getexif()

            old_software_value = (
                exif_data.get(software_tag_id, "不明")
                if software_tag_id is not None
                else "なし"
            )
            old_date_time_value = exif_data.get(date_time_tag_id, "未設定")

            # ── [ステップ4] Software タグの復元（設定または削除） ──
            if software_tag_id is not None:
                if restored_software_value is None:
                    # 元々 Software タグが存在しないカメラ画像の場合はタグをポップ（削除）
                    exif_data.pop(int(software_tag_id), None)
                    restored_software_disp = "削除 (なし)"
                else:
                    # 元々 Software タグが存在していた場合は元の文字列を復元
                    exif_data[int(software_tag_id)] = restored_software_value
                    restored_software_disp = f"'{restored_software_value}'"
            else:
                restored_software_disp = "なし"

            # ── [ステップ5] DateTime タグの復元 ──
            exif_data[int(date_time_tag_id)] = original_date_time_value

            # 画像への上書き保存
            current_image.save(image_path, exif=exif_data)

            if not is_simple_mode:
                print(f"[Exif復元完了] {image_path}")
                print(
                    f"  ・Software : '{old_software_value}' -> {restored_software_disp}"
                )
                print(
                    f"  ・DateTime : '{old_date_time_value}' -> '{original_date_time_value}'"
                )
            return True

    except Exception as error_message:
        if not is_simple_mode:
            print(
                f"エラー: Exif 復元書き込み中にエラーが発生しました -> {error_message}"
            )
        return False


def process_image_file_automatically(
    image_path: str, database_file_path: str, is_simple_mode: bool = False
) -> bool:
    """Software タグの値を検査し、Gimp 文字列が含まれるかに応じて

    『DB登録』か『Exif復元』かを自動判定して実行します。

    Args:
        image_path (str): 対象画像ファイルのパス
        database_file_path (str): JSON データベースのファイルパス
        is_simple_mode (bool): 簡易表示モードフラグ（デフォルト: False）

    Returns:
        bool: 処理成功時 (スキップ含) True, エラー時 False
    """
    if not is_simple_mode:
        print(f"\n[処理開始] 画像ファイル: {image_path}")

    # ── [ステップ1] Software タグ文字列の解析 ──
    software_value = get_exif_tag_value_by_name(image_path, "Software")

    # ── [ステップ2] Gimp 書き換え判定と処理の自動分岐 ──
    if software_value and "gimp" in software_value.lower():
        if not is_simple_mode:
            print(
                "判定結果: Gimp による書き換えを検知しました -> 【復元モード】を実行します"
            )
        is_success = restore_exif_data_from_gimp(
            image_path, database_file_path, is_simple_mode
        )
        if is_simple_mode:
            status_text = "[復元]" if is_success else "[Error]"
            print(f"{status_text} {image_path}")
        return is_success
    else:
        if not is_simple_mode:
            print(
                "判定結果: オリジナル画像（Gimp未検知）です -> 【DB自動登録モード】を実行します"
            )
        result_status = register_original_software_database(
            image_path, database_file_path, is_simple_mode
        )
        if is_simple_mode:
            if result_status in ("REGISTERED", "UPDATED"):
                status_text = "[登録]"
            elif result_status == "SKIPPED":
                status_text = "[Skip]"
            else:
                status_text = "[Error]"
            print(f"{status_text} {image_path}")

        return result_status != "ERROR"


def main() -> None:
    """メイン処理を実行します。

    Returns:
        None
    """
    if len(sys.argv) < 2:
        print("使用方法: python 05_exif_restore_from_gimp.py <対象画像ファイルのパス>")
        sys.exit(1)

    target_image_path = sys.argv[1]

    if not os.path.exists(target_image_path):
        print(f"エラー: 指定されたファイルが存在しません -> {target_image_path}")
        sys.exit(1)

    process_image_file_automatically(
        target_image_path, JSON_DATABASE_FULL_PATH, is_simple_mode=False
    )


if __name__ == "__main__":
    main()
