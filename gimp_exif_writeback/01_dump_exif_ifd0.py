import sys
from typing import Dict, Any, Optional
from PIL import Image, ExifTags


def get_exif_data(image_path: str) -> Optional[Dict[str, Any]]:
    """
    指定されたJPEG画像ファイルからExifデータを抽出し、タグ名をキーとした辞書形式で返します。

    Args:
        image_path (str): 読み込むJPEG画像ファイルのパス

    Returns:
        Optional[Dict[str, Any]]: Exifタグ名と値の辞書。Exif情報がない場合はNone
    """
    try:
        # ── [ステップ1] 画像ファイルのオープン ──
        # PILを使用して画像ファイルを開きます
        with Image.open(image_path) as current_image:
            # 画像からExifデータを取得します
            raw_exif = current_image.getexif()

            # Exifデータが存在しない場合は処理を終了します
            if not raw_exif:
                return None

            # ── [ステップ2] タグIDから可読なタグ名への変換 ──
            # ID形式のキー（例: 271）を人間が読める文字列（例: 'Make'）に変換します
            parsed_exif_data: Dict[str, Any] = {}
            for tag_id, value in raw_exif.items():
                # 定義されているExifタグ名を取得し、未定義の場合はIDをそのまま使用します
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                parsed_exif_data[tag_name] = value

            return parsed_exif_data

    except FileNotFoundError:
        print(f"エラー: 指定されたファイルが見つかりません -> {image_path}")
        return None
    except Exception as error_message:
        print(f"エラー: 画像の読み込み中にエラーが発生しました -> {error_message}")
        return None


def print_exif_data(image_path: str) -> None:
    """
    指定されたJPEG画像のExifタグ一覧をコンソールに出力します。

    Args:
        image_path (str): 対象とするJPEG画像ファイルのパス

    Returns:
        None
    """
    print(f"=== ファイル: {image_path} のExif情報 ===")

    # ── [ステップ1] Exif データの取得 ──
    exif_information = get_exif_data(image_path)

    # ── [ステップ2] 取得結果の条件分岐と表示処理 ──
    if not exif_information:
        print("Exif情報が見つかりませんでした。")
        return

    # 取得したタグと値を順番に整形して出力します
    for tag_name, tag_value in exif_information.items():
        print(f"{tag_name}: {tag_value}")


if __name__ == "__main__":
    # ── [ステップ1] コマンドライン引数の確認 ──
    # スクリプト実行時に画像パスが渡されているかチェックします
    if len(sys.argv) < 2:
        print("使用方法: python display_exif.py <画像ファイルのパス>")
        sys.exit(1)

    # 第一引数を画像パスとして使用します
    target_image_path = sys.argv[1]

    # ── [ステップ2] メイン処理の実行 ──
    print_exif_data(target_image_path)