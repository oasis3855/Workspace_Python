#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE Classic 1K のセクタ鍵 (Key A) を変更するスクリプト。

このモジュールは、指定されたセクタの鍵を現在の鍵（旧鍵）で認証し、
新しい鍵へ書き換えます。セクタトレーラのアクセス条件（Access Bits）を
標準値 (FF 07 80 69) に保つことで、安全に鍵のみを変更します。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/04/09)
    1.1.0 (2026/04/13) - 読み取り確認プロセスおよびKey A/B個別定義の追加。
"""

from smartcard.util import toHexString
from smartcard.System import readers


def get_mifare_type(conn) -> str:
    """ATRを取得し、MIFARE Classic 1K, 4K, またはそれ以外かを判定する。

    Returns:
        "1K", "4K", または "Unknown"
    """
    atr = conn.getATR()
    # PCSC標準のMIFARE ATR構造において、
    # インデックス12:15 (SS, C0, C1) がカード種別を示す
    # 03 00 01 = 1K, 03 00 02 = 4K
    try:
        if len(atr) >= 15:
            if atr[0:12] != [0x3B, 0x8F, 0x80, 0x01, 0x80,
                             0x4F, 0x0C, 0xA0, 0x00, 0x00, 0x03, 0x06]:
                return "Unknown"
            card_code = atr[12:15]
            if atr[12:15] == [0x03, 0x00, 0x01]:
                return "1K"
            elif atr[12:15] == [0x03, 0x00, 0x02]:
                return "4K"
    except Exception:
        pass
    return "Unknown"


def main() -> None:
    """メイン実行関数。セクタ0の鍵を変更する。"""
    print("--- MIFARE Classic 1K Key Change Tool ---")

    TARGET_SECTOR = 1
    TRAILER_BLOCK = (TARGET_SECTOR * 4) + 3  # セクタ0ならBlock 3

    # 今回の認証に使用する鍵（カードに現在設定されている鍵）
    # OLD_AUTH_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    OLD_AUTH_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
    # 変更後の新しい鍵定義
    # NEW_TYPE_A_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
    NEW_TYPE_A_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    NEW_TYPE_B_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]

    # アクセス条件 (デフォルト: フルアクセス)
    ACCESS_BITS = [0xFF, 0x07, 0x80, 0x69]

    try:
        reader_list = readers()
        if not reader_list:
            return

        reader = reader_list[0]
        print("using RFID reader : " + str(reader).split('[')[0].strip())

        conn = reader.createConnection()
        conn.connect()

        # --- カードタイプの自動判定 ---
        mifare_type = get_mifare_type(conn)

        if mifare_type == "1K":
            print("Detected: MIFARE Classic 1K")
        else:
            print("Detected Tag is not MIFARE Classic 1K.  Script Abort.")
            return

        # 1. 旧鍵をリーダの揮発メモリNo.1にロード
        print(f"Loading Old Key: {toHexString(OLD_AUTH_KEY)}")
        LOAD_KEY_APDU = [0xFF, 0x82, 0x00, 0x00, 0x06] + OLD_AUTH_KEY
        conn.transmit(LOAD_KEY_APDU)

        # 2. 認証（リーダの揮発メモリNo.1と、RFIDタグのType Aによる）
        print(f"Authenticating Sector {TARGET_SECTOR}...")
        AUTH_APDU = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, TRAILER_BLOCK, 0x60, 0x00]
        _, sw1, _ = conn.transmit(AUTH_APDU)

        if sw1 != 0x90:
            print(f"Error: 旧鍵での認証に失敗しました。(SW1: {hex(sw1)})")
            return

        # 3. 現在のトレーラー・ブロックを読み出す (Read Binary)
        # APDU: [FF B0 00 block size]
        READ_BINARY_APDU = [0xFF, 0xB0, 0x00, TRAILER_BLOCK, 0x10]
        current_trailer, sw1, _ = conn.transmit(READ_BINARY_APDU)

        if sw1 != 0x90:
            print(f"Error: 現在のトレーラー・ブロックの読み込みに失敗しました (SW1: {hex(sw1)})")
            return

        print(f"\n[Current Status]")
        print(f"Sector {TARGET_SECTOR:02d} Trailer (Block {TRAILER_BLOCK:03d}):")
        print(f"Data: {toHexString(current_trailer)}")

        # 4. 新しいトレーラーデータの構築
        # [Key A (6b)] + [Access Bits (4b)] + [Key B (6b)]
        new_trailer_data = NEW_TYPE_A_KEY + ACCESS_BITS + NEW_TYPE_B_KEY

        print(f"\n[New Configuration]")
        print(f"New Key A      : {toHexString(NEW_TYPE_A_KEY)}")
        print(f"Access Bits    : {toHexString(ACCESS_BITS)}")
        print(f"New Key B      : {toHexString(NEW_TYPE_B_KEY)}")
        print(f"Final Payload  : {toHexString(new_trailer_data)}")

        # 5. ユーザー確認
        print("\n!!! WARNING !!!")
        print("アクセスビットや鍵の書き込みに失敗すると、このセクタは永久にロックされる可能性があります。")
        confirm = input(f"セクタ {TARGET_SECTOR} の鍵を更新しますか？ [y/N]: ").strip().lower()

        if confirm != 'y':
            print("操作を中止しました。")
            return

        # 6. 書き込み実行 (Update Binary)
        print("書き込みを実行中...")
        UPDATE_BINARY_APDU = [0xFF, 0xD6, 0x00, TRAILER_BLOCK, 0x10] + new_trailer_data
        _, sw1, sw2 = conn.transmit(UPDATE_BINARY_APDU)

        if sw1 == 0x90:
            print(f"\n[SUCCESS] セクタ {TARGET_SECTOR} の鍵とアクセスビットを更新しました。")
            print(f"次回からの認証には新しい鍵を使用してください。")
        else:
            print(f"\n[FAILED] 書き込みエラー (SW1: {hex(sw1)}, SW2: {hex(sw2)})")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.disconnect()  # type: ignore


if __name__ == "__main__":
    main()
