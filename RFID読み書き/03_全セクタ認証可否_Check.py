#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE Classic 1K カードの書き込み可否および有効容量をチェックするスクリプト。

このモジュールは、標準のトランスポートキー（FF FF FF FF FF FF）を使用して
全16セクタの認証を試行し、各セクタが書き込み可能な状態（工場出荷時設定）
であるかを確認します。また、使用可能なブロック数から総バイト容量を算出します。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ (pip install pyscard)

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/03/27)
    1.0.1 (2026/04/13) ATRでClassic 1K/4Kを自動判定
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


def main():
    print("--- MIFARE Classic 1K/4K Capacity & Write-Check ---")

    try:
        reader_list = readers()
        if not reader_list:
            print("Error: リーダーが見つかりません。")
            return

        reader = reader_list[0]
        print("using RFID reader : " + str(reader).split('[')[0].strip())

        conn = reader.createConnection()
        conn.connect()

        # --- カードタイプの自動判定 ---
        mifare_type = get_mifare_type(conn)

        TOTAL_SECTORS = 16
        if mifare_type == "1K":
            print("Detected: MIFARE Classic 1K")
        elif mifare_type == "4K":
            TOTAL_SECTORS = 40
            print("Detected: MIFARE Classic 4K")
        else:
            print(f"Unknown Card Type (ATR: {toHexString(conn.getATR())})")
            return

        # 認証キー
        AUTH_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        # AUTH_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
        # AUTH_KEY = [0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5]

        # 認証キーをリーダーの揮発メモリNo.1にロード
        LOAD_KEY_APDU = [0xFF, 0x82, 0x00, 0x00, 0x06] + AUTH_KEY
        conn.transmit(LOAD_KEY_APDU)

        print("load auth key = " + toHexString(AUTH_KEY))

        writable_blocks = 0

        print(f"Checking {TOTAL_SECTORS} sectors...")
        print("Sector | Status | Capacity")
        print("---------------------------")

        for sector in range(TOTAL_SECTORS):
            # セクタの最初のブロック番号 (0, 4, 8, ..., 128, 144, )
            target_block = sector * 4
            if sector >= 32:
                # MIFARE Classic 4K対応のセクタ/ブロック計算
                target_block = 32 * 4 + (sector - 32) * 16

            # 1. 認証（リーダの揮発メモリNo.1と、RFIDタグのType Aによる）
            AUTH_APDU = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, target_block, 0x60, 0x00]
            res, sw1, sw2 = conn.transmit(AUTH_APDU)

            if sw1 == 0x90:
                # 認証成功 = このセクタのデータブロック(3つ)は書き込み可能と推測
                # (セクタ0のブロック0は通常Read Onlyなので除外するのが一般的)
                usable_in_this_sector = 3
                if sector == 0:
                    usable_in_this_sector = 2
                elif sector >= 32:
                    # MIFARE Classic 4K対応のセクタ/ブロック計算
                    usable_in_this_sector = 15

                writable_blocks += usable_in_this_sector
                print(f"  {sector:02d}   |  OK    | {usable_in_this_sector * 16} bytes")
            else:
                print(f"  {sector:02d}   | AUTH FAILED (sw1:{sw1:02x}, sw2:{sw2:02x})")

        print("---------------------------")
        total_bytes = writable_blocks * 16
        print(f"Total Writable Capacity: {total_bytes} bytes")
        print(f"Max Records (if 16B/rec): {writable_blocks} records")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.disconnect()  # type: ignore


if __name__ == "__main__":
    main()
