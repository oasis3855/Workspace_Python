#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE Classic 1K の全データブロックを読み出し、16進数とASCIIでダンプするスクリプト。

このモジュールは、認証に成功したセクタ内のデータブロック（各セクタのBlock 0-2）
の内容を順次読み出し、コンソールに整形して出力します。カード内の既存データの
確認や、書き込み後の検証に使用します。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/03/27)
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
    print("--- MIFARE Classic 1K Full Data Dump ---")

    try:
        reader_list = readers()
        if not reader_list:
            print("Error: リーダーが見つかりません。")
            return

        # --- Sector Trailerを表示するかどうか選択プロンプト ---
        BLOCKS_PER_SECTOR = 3
        confirm = input("\n各セクタ最終ブロック Sector Trailer を表示しますか [y/N] : ").strip().lower()
        if confirm == 'y':
            BLOCKS_PER_SECTOR = 4

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

        # 認証キー
        AUTH_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        # AUTH_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
        # AUTH_KEY = [0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5]

        # 認証キーをリーダーの揮発メモリNo.1にロード
        LOAD_KEY_APDU = [0xFF, 0x82, 0x00, 0x00, 0x06] + AUTH_KEY
        conn.transmit(LOAD_KEY_APDU)

        print("load auth key = " + toHexString(AUTH_KEY))

        print(f"{'Sector':<6} | {'Block':<5} | {'Data (Hex Dump)':<47} | {'ASCII'}")
        print("-" * 84)

        TOTAL_SECTORS = 16      # MIFARE Classic 1K

        for sector in range(TOTAL_SECTORS):
            target_block = sector * 4

            # 1. 認証（リーダの揮発メモリNo.1と、RFIDタグのType Aによる）
            AUTH_APDU = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, target_block, 0x60, 0x00]
            _, sw1, sw2 = conn.transmit(AUTH_APDU)

            if sw1 != 0x90:
                print(f"  {sector:02d}   |  ---  | Authentication Failed")
                continue

            # 2. セクタ内のブロック(0〜2)を読み出す (3は鍵情報なので読み飛ばす)
            for b in range(BLOCKS_PER_SECTOR):
                current_block = target_block + b
                # READコマンド: [FF, B0, 00, ブロック番号, 読み出しバイト数(16)]
                READ_BINARY_APDU = [0xFF, 0xB0, 0x00, current_block, 0x10]
                data, s1, s2 = conn.transmit(READ_BINARY_APDU)

                if s1 == 0x90:
                    hex_dump = toHexString(data)
                    # ASCII表示（制御文字などはドットに置換）
                    ascii_dump = "".join([chr(x) if 32 <= x <= 126 else "." for x in data])
                    print(f"  {sector:02d}   |  {current_block:03d}  | {hex_dump} | {ascii_dump}")
                else:
                    print(f"  {sector:02d}   |  {current_block:03d}  | Read Error")

            print("-" * 84)  # セクタごとの区切り

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.disconnect()  # type: ignore


if __name__ == "__main__":
    main()
