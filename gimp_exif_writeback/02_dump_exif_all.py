#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""JPEG画像ファイルからサブIFDを含む全Exif情報を抽出しフォーマット出力するスクリプト。

このモジュールは、Pillow (PIL) ライブラリを使用してJPEG画像内に格納されている
メイン領域(IFD0)、詳細情報(ExifIFD)、位置情報(GPSInfo)などの各種Exifタグ情報を網羅的に抽出し、
16進数ダンプ、制御文字のエスケープ処理、APEX規格（F値やシャッタースピード）の人間が読みやすい形式への
自動変換を行った上で、整形されたテキストとしてコンソールに出力します。

Attributes:
    なし (コマンドライン引数より画像ファイルパスを受け取って処理します)

Requires:
    - Python 3.x
    - Pillow (PIL): 画像処理・Exifデータ解析用ライブラリ (pip install Pillow)

Author:
    Google Gemini3.6 Flash Collaborating Coding

Version:
    1.0.0 (2026/08/13)
"""

import sys
import math
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ExifTags


def convert_bytes_to_hex_dump(raw_bytes: bytes, max_display_bytes: int = 16) -> str:
    """
    バイト列（bytes）を1バイトずつ "0xXX" 形式の16進数表現スペース区切りテキストに変換します。
    指定されたバイト数を超える場合は、後ろを切り捨てて末尾に "..." を付与します。

    Args:
        raw_bytes (bytes): 変換対象のバイナリデータ
        max_display_bytes (int): 表示する最大バイト数（デフォルト: 16）

    Returns:
        str: "0x00 0x25 0x33 ..." のような省略付き16進数ダンプ文字列
    """
    # ── [ステップ1] バイト列の切り捨て判定 ──
    is_truncated = len(raw_bytes) > max_display_bytes
    target_bytes = raw_bytes[:max_display_bytes] if is_truncated else raw_bytes

    # ── [ステップ2] 16進数文字列へのフォーマット ──
    # 切り捨てされたバイト列を16進数形式に変換し、スペースで連結する
    hex_string = " ".join(f"0x{byte_value:02x}" for byte_value in target_bytes)

    if is_truncated:
        hex_string += " ..."

    return hex_string


def sanitize_string_value(text_value: str) -> str:
    """
    文字列中に含まれる改行文字（\r, \n, \t）をエスケープシーケンス文字に置換し、可読化します。

    Args:
        text_value (str): 対象の文字列

    Returns:
        str: エスケープシーケンス文字を置換した安全な文字列
    """
    # 改行文字やタブ文字をエスケープシーケンスとして置換する
    sanitized_text = text_value.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return sanitized_text


def convert_apex_to_human_readable(tag_name: str, raw_value: Any) -> Any:
    """
    APEX規格などのExif数値を人間が読みやすい形式（F値、1/X秒）に変換します。

    Args:
        tag_name (str): Exifタグの名前
        raw_value (Any): 変換前のExif生の数値

    Returns:
        Any: 人間が読みやすい形式に変換された文字列、または元の値
    """
    try:
        float_value = float(raw_value)

        # ── [ステップ1] ApertureValue（APEX絞り値）を F値 に変換 ──
        if tag_name.endswith("ApertureValue"):
            # 計算式: F = 2 ^ (ApertureValue / 2)
            f_number = math.pow(2, float_value / 2.0)
            return f"f/{f_number:.1f} (RAW APEX: {raw_value})"

        # ── [ステップ2] ShutterSpeedValue（APEXシャッタースピード値）を 秒数（1/X秒） に変換 ──
        if tag_name.endswith("ShutterSpeedValue"):
            # 計算式: Exposure Time = 2 ^ (-ShutterSpeedValue)
            seconds = math.pow(2, -float_value)
            if 0 < seconds < 1.0:
                # 1/X秒形式に変換
                denominator = round(1.0 / seconds)
                return f"1/{denominator} sec (RAW APEX: {raw_value})"
            else:
                # 秒数形式で返す
                return f"{seconds:.2f} sec (RAW APEX: {raw_value})"

    except (ValueError, TypeError, OverflowError):
        # 数値変換ができない型やエラーの場合は変換せず元の値を返す
        pass

    return raw_value


def format_exif_value(tag_name: str, value: Any) -> str:
    """
    Exifのデータ型（バイナリ、文字列、APEX数値等）を判定し、適切なテキスト表現に整形します。

    Args:
        tag_name (str): Exifタグの名前
        value (Any): 変換判定を行うExifデータ値

    Returns:
        str: フォーマット済みのテキスト文字列
    """
    # ── [ステップ1] 単体バイト列の変換 ──
    if isinstance(value, bytes):
        # バイト列は16進数ダンプとして表示
        return convert_bytes_to_hex_dump(value)

    # ── [ステップ2] タプルやリスト構造内の変換 ──
    if isinstance(value, (tuple, list)):
        formatted_items: List[str] = []
        for item in value:
            if isinstance(item, bytes):
                formatted_items.append(convert_bytes_to_hex_dump(item))
            elif isinstance(item, str):
                formatted_items.append(sanitize_string_value(item))
            else:
                # 数値やその他の型はそのまま文字列化
                formatted_items.append(str(item))
        # リスト形式で内部の要素を括弧で囲んで返す
        return f"({', '.join(formatted_items)})"

    # ── [ステップ3] 文字列型の制御文字置換変換 ──
    if isinstance(value, str):
        # 単純な文字列は可読化処理を適用
        return sanitize_string_value(value)

    # ── [ステップ4] APEX値などの人間向け変換 ──
    # 上記のいずれにも該当しない場合は、APEX変換を試みる
    converted_apex = convert_apex_to_human_readable(tag_name, value)
    return str(converted_apex)


def get_all_exif_data_with_metadata(image_path: str) -> Optional[List[Tuple[int, str, str]]]:
    """
    指定されたJPEG画像からサブIFDを含めた全Exifタグを抽出し、(tag_id, formatted_tag_name, formatted_value) のリストを返します。

    Args:
        image_path (str): 読み込むJPEG画像ファイルのパス

    Returns:
        Optional[List[Tuple[int, str, str]]]: タグ情報のタプルリスト。Exif情報が存在しない場合はNone
    """
    try:
        # ── [ステップ1] 画像ファイルのオープンとExif情報の取得 ──
        with Image.open(image_path) as current_image:
            raw_exif = current_image.getexif()

            if not raw_exif:
                # Exif情報が全くない場合はリストを返さない
                return None

            exif_records: List[Tuple[int, str, str]] = []

            # ── [ステップ2] IFD0（メイン領域）のタグ解析 ──
            for tag_id, raw_value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

                # 特定のタグはスキップ（情報が重複または不要な場合）
                if tag_name in ("ExifOffset", "GPSInfo"):
                    continue

                # タグ名を整形し、値のフォーマットを適用
                formatted_tag_name = f"[IFD0] {tag_name}"
                formatted_value = format_exif_value(formatted_tag_name, raw_value)
                exif_records.append((tag_id, formatted_tag_name, formatted_value))

            # ── [ステップ3] サブIFD（ExifIFD / 詳細情報）の取得 ──
            try:
                exif_ifd_content = raw_exif.get_ifd(ExifTags.IFD.Exif)
                if exif_ifd_content:
                    for sub_tag_id, sub_raw_value in exif_ifd_content.items():
                        sub_tag_name = ExifTags.TAGS.get(sub_tag_id, str(sub_tag_id))
                        formatted_tag_name = f"[ExifIFD] {sub_tag_name}"
                        formatted_value = format_exif_value(formatted_tag_name, sub_raw_value)
                        exif_records.append((sub_tag_id, formatted_tag_name, formatted_value))
            except Exception:
                # サブIFDの読み込みでエラーが発生しても続行
                pass

            # ── [ステップ4] サブIFD（GPSInfo / 位置情報）の取得 ──
            try:
                gps_ifd_content = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd_content:
                    for gps_tag_id, gps_raw_value in gps_ifd_content.items():
                        gps_tag_name = ExifTags.GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                        formatted_tag_name = f"[GPSInfo] {gps_tag_name}"
                        formatted_value = format_exif_value(formatted_tag_name, gps_raw_value)
                        exif_records.append((gps_tag_id, formatted_tag_name, formatted_value))
            except Exception:
                # GPS情報の読み込みでエラーが発生しても続行
                pass

            return exif_records

    except FileNotFoundError:
        print(f"エラー: 指定されたファイルが見つかりません -> {image_path}")
        return None
    except Exception as error_message:
        print(f"エラー: 画像の読み込み中に予期せぬエラーが発生しました -> {error_message}")
        return None


def print_all_exif_data(image_path: str) -> None:
    """
    すべてのExifタグ情報を tag_id(int), tag_name(str), formatted_value(str) の固定幅フォーマットで出力します。

    Args:
        image_path (str): 対象とするJPEG画像ファイルのパス

    Returns:
        None
    """
    print(f"=== ファイル: {image_path} の全Exif情報 ===")

    # ── [ステップ1] Exifレコードの取得 ──
    exif_records = get_all_exif_data_with_metadata(image_path)

    if not exif_records:
        print("Exif情報が見つかりませんでした。")
        return

    # ── [ステップ2] タグID順にソート ──
    # IFDの領域（[IFD0], [ExifIFD], [GPSInfo]）ごとにグループ化し、その中でタグID順にソートします
    ifd_order = {"[IFD0]": 0, "[ExifIFD]": 1, "[GPSInfo]": 2}

    def sort_key(record: Tuple[int, str, str]) -> Tuple[int, int]:
        prefix = record[1].split()[0]  # "[IFD0]" などを抽出
        order = ifd_order.get(prefix, 99)
        return (order, record[0])

    sorted_records = sorted(exif_records, key=sort_key)

    # ── [ステップ3] 固定幅でコンソール表示 ──
    # ヘッダー行を出力
    print(f"{'ID':>5} | {'Tag Name':<32} | Value")
    print("-" * 80)

    # 各レコードを出力
    for tag_id, tag_name, formatted_value in sorted_records:
        print(f"{tag_id:5d} | {tag_name:<32} | {formatted_value}")


if __name__ == "__main__":
    # スクリプト実行時の引数チェック
    if len(sys.argv) < 2:
        print("使用方法: python 02_dump_exif_all.py <画像ファイルのパス>")
        sys.exit(1)

    target_image_path = sys.argv[1]
    # 画像パスが提供された場合、Exif情報を出力する処理を実行
    print_all_exif_data(target_image_path)
