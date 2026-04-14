#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE Classic 1K の Sector 0 / Block 0 (UID領域) の書き換え可否をテストするスクリプト。

このモジュールは、通常のカードでは読み取り専用である Block 0 に対して書き込みを試行します。
CUID (Magic Chinese Card Gen2) などの特殊なカードであれば、UIDの書き換えが可能です。
指定された4バイトのUIDに基づき、BCC (チェックサム) を自動計算して書き込みデータを生成します。

Attributes:
    TARGET_BLOCK (int):     書き込み対象のブロック番号（常に 0）。
    UID_BYTES (list):       設定したい4バイトのUID（16進数リスト）。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/04/09) - BCC自動計算機能を含むUID書き換えテスト版の作成。
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
    """メイン実行関数。Block 0を読み取り、UID/BCCのみを差し替えて書き込みを実行する。"""
    print("--- MIFARE Classic 1K UID Write Test (Read-Modify-Write) ---")

    TARGET_BLOCK = 0
    # 書き換えたい新しいUID
    UID_BYTES = [0x01, 0x02, 0x03, 0x04]

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

        # 3. 現在の Block 0 を読み取る
        READ_BINARY_APDU = [0xFF, 0xB0, 0x00, TARGET_BLOCK, 0x10]
        current_data, sw1, _ = conn.transmit(READ_BINARY_APDU)
        if sw1 != 0x90:
            print("Error: 現存データの読み取りに失敗しました。")
            return

        print(f"Current Block 0: {toHexString(current_data)}")

        # 4. BCC (Check Byte) の計算
        bcc = 0
        for byte in UID_BYTES:
            bcc ^= byte

        # 5. 書き込みデータの合成
        # [UID(4b)] + [BCC(1b)] + [元のデータの5バイト目以降(11b)]
        # current_data[5:16] には SAK, ATQA, Manufacturer Data が含まれる
        write_data = UID_BYTES + [bcc] + current_data[5:16]

        print(f"New UID        : {toHexString(UID_BYTES)}")
        print(f"Calculated BCC : {hex(bcc)}")
        print(f"Final Payload  : {toHexString(write_data)}")

        # --- 最終確認プロンプト ---
        confirm = input("\nこの内容で書き込みますか [y/N] : ").strip().lower()
        if confirm != 'y':
            print("書き込みをキャンセルしました。")
            return

        # 4. 書き込み実行 (UPDATE BINARY)
        # [CLA=FF, INS=D6, P1=00, P2=ブロック番号, Lc=10(16バイト), Data...]
        UPDATE_BINARY_APDU = [0xFF, 0xD6, 0x00, TARGET_BLOCK, 0x10] + write_data
        _, sw1, sw2 = conn.transmit(UPDATE_BINARY_APDU)

        if sw1 == 0x90:
            print("Success: 書き込みが完了しました。UIDが更新されました。")
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
