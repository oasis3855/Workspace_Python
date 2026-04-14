#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE Classic 1K の指定ブロックに16バイトのデータを書き込むスクリプト。

このモジュールは、指定された文字列（ASCII）を16バイトの固定長データに整形し、
カードの特定ブロックへ書き込みます。書き込み前には該当セクタへの認証を行い、
書き込みの成否をステータスコードで判定します。

Attributes:
    TARGET_BLOCK (int):     書き込み対象のブロック番号（デフォルト: 1）。
    WRITE_TEXT_DATA (str):       書き込む文字列（最大16バイト）。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/03/27)
    1.1.0 (2026/04/09) - 書き込みモード選択機能（対話型プロンプト）の追加。
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
    print("--- MIFARE Classic 1K Block Write ---")

    # 書き込みデータの設定
    TARGET_BLOCK = 1
    WRITE_TEXT_DATA = "test test test"

    # --- モード選択プロンプト ---
    print(f"\n[Target: Block {TARGET_BLOCK:03d}]")
    print(f"1: '{WRITE_TEXT_DATA}' を書き込む")
    print("2: NULLクリア (全0書き込み) する")
    print("q: キャンセルして終了")

    choice = input("\n実行する操作を選択してください (1/2/q): ").strip().lower()

    if choice == '1':
        print(f"モード: 文字列書き込み ('{WRITE_TEXT_DATA}')")
        raw_payload = WRITE_TEXT_DATA.encode('ascii')
    elif choice == '2':
        print("モード: NULLクリア")
        raw_payload = b""  # 空のバイト列（後で0埋めされる）
    elif choice == 'q':
        print("操作をキャンセルしました。")
        return
    else:
        print("無効な選択です。終了します。")
        return

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

        if mifare_type == "1K":
            print("Detected: MIFARE Classic 1K")
        else:
            print("Detected Tag is not MIFARE Classic 1K.  Script Abort.")
            return

        # 認証キー
        AUTH_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        # AUTH_KEY = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
        # AUTH_KEY = [0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5]

        # 1. 認証キーをリーダーの揮発メモリNo.1にロード
        LOAD_KEY_APDU = [0xFF, 0x82, 0x00, 0x00, 0x06] + AUTH_KEY
        conn.transmit(LOAD_KEY_APDU)

        # 2. 認証 (ターゲットブロックが属するセクタに対して実行)
        # 第8引数はセクタ内のどのブロックを指定してもOK
        AUTH_APDU = [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00, TARGET_BLOCK, 0x60, 0x00]
        _, sw1, sw2 = conn.transmit(AUTH_APDU)

        if sw1 != 0x90:
            print(f"Error: 認証に失敗しました (SW1: {hex(sw1)})")
            return

        # 3. データの整形 (16バイト固定にする)
        write_data = list(raw_payload)
        # 16バイトに足りない分を 0x00 で埋める（NULLクリア時はここで全0になる）
        write_data += [0x00] * (16 - len(write_data))
        # 16バイトを超えていたらカット
        write_data = write_data[:16]

        print(f"Writing to Block {TARGET_BLOCK:03d}")
        print(f"Hex Data: {toHexString(write_data)}")

        # 4. 書き込み実行 (UPDATE BINARY)
        # [CLA=FF, INS=D6, P1=00, P2=ブロック番号, Lc=10(16バイト), Data...]
        UPDATE_BINARY_APDU = [0xFF, 0xD6, 0x00, TARGET_BLOCK, 0x10] + write_data
        _, sw1, sw2 = conn.transmit(UPDATE_BINARY_APDU)

        if sw1 == 0x90:
            print("Success: 書き込みが完了しました。")
        else:
            print(f"Failed: 書き込みエラー (SW1: {hex(sw1)}, SW2: {hex(sw2)})")

    except Exception as e:
        print(f"Exception: {e}")
    finally:
        # VSCodeの警告を無視して安全に閉じる
        if 'conn' in locals():
            conn.disconnect()  # type: ignore


if __name__ == "__main__":
    main()
