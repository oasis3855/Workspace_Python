#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ACR1251Uリーダーを使用してRFID（FeliCa/MIFARE）のIDを厳密にチェック・読み取るスクリプト。

このモジュールは、ICカードのATR（Answer to Reset）を解析し、特定のPrefixおよび
RID（Registered Application Provider Identifier）を確認することで、意図しない
カードの誤認識を防ぎます。FeliCaおよび各種MIFARE規格を自動判別し、
それぞれの規格に応じた固有ID（IDm/UID）を取得して表示します。

Attributes:
    CMD_GET_IDM (list):     FeliCa/MIFAREからIDm/UIDを取得するためのAPDUコマンド。
    CMD_GET_PMM (list):     FeliCaからPMm（製造パラメータ）を取得するためのAPDUコマンド。
    MIFARE_TYPES (dict):    ATRのC0/C1バイトに基づくMIFAREカード種別のマッピング辞書。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ (pip install pyscard)
    - PC/SC デーモン (Linux環境では pcscd が動作していること)

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/03/27) - 初版完成：ATR厳密チェックおよび例外処理の実装。
"""

from smartcard.util import toHexString
from smartcard.System import readers
from smartcard.pcsc.PCSCExceptions import EstablishContextException

# コマンド定義
GET_DATA_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]
GET_DATA_ATS_APDU = [0xFF, 0xCA, 0x01, 0x00, 0x00]

# MIFARE Card Name (C0 C1) マッピング
MIFARE_TYPES = {
    "00 01": "MIFARE Classic 1K",
    "00 02": "MIFARE Classic 4K",
    "00 03": "MIFARE Ultralight",
    "00 04": "MIFARE DESFire",
    "00 26": "MIFARE Mini",
    "00 30": "MIFARE DESFire EV1",
    "00 36": "MIFARE Plus SL1 2K",
    "00 37": "MIFARE Plus SL1 4K",
    "00 38": "MIFARE Plus SL2 2K",
    "00 39": "MIFARE Plus SL2 4K",
}


def main() -> None:
    """メイン実行関数。リーダーの検知、カード接続、ATR解析、ID取得の一連のフローを制御する。"""
    print("--- RFID Strict-Check Reader (ACR1251U) ---")

    try:
        reader_list = readers()
    except EstablishContextException:
        print("Error: PCSCサービスが起動していません。")
        return

    if not reader_list:
        print("Error: リーダーが見つかりません。")
        return

    reader = reader_list[0]
    conn = reader.createConnection()
    try:
        conn.connect()
    except Exception:
        # カードがない、未対応カード、リーダーエラーなど全てをここでキャッチ
        print("Error: カードが置かれていないか、読み取れないカードです。")
        return

    try:
        # ATR取得と表示
        atr = conn.getATR()
        atr_hex_list = toHexString(atr).split()
        print(f"Full ATR: {' '.join(atr_hex_list)}")

        # --- 1. Prefix チェック (0-6バイト目) ---
        # ISO14443-3準拠のATR開始バイトを確認
        if len(atr) < 7 or toHexString(atr[0:7]) != "3B 8F 80 01 80 4F 0C":
            print(f"Error: 不明なATR Prefixです (Actual: {toHexString(atr[0:7])})")
            return

        # --- 2. RID チェック (7-11バイト目) ---
        # PC/SC規格におけるRID（A0 00 00 03 06）を確認
        if len(atr) < 12 or toHexString(atr[7:12]) != "A0 00 00 03 06":
            print(f"Error: RIDが一致しません (Actual: {toHexString(atr[7:12])})")
            return

        print(
            "ATR Header:T0:TD1:TD2:T1 = 3B:8F:80:01:80, Tk[0]:Tk[1] = 4F:0C, Tk[RID] = A0 00 00 03 06")

        # --- 3. SS (12バイト目) による仕分け ---
        # Standard Special(SS)バイトにより規格を判定
        ss = atr[12]

        # C0 C1 取得 (13, 14バイト目)
        c0c1_str = toHexString(atr[13:15]) if len(atr) >= 15 else "Unknown"

        if ss == 0x11:
            # FeliCa チェック
            if c0c1_str != "00 3B":
                print(f"Error: FeliCa拡張バイト(C0:C1)が一致しません (Actual: {c0c1_str})")
                return

            print(f"Type: FeliCa (Validated, ss=11, c0:c1=00 3B)")
            res_uid, sw1, sw2 = conn.transmit(GET_DATA_UID_APDU)
            status_uid = "読み出し正常" if (sw1 == 0x90 and sw2 == 0x00) else "読み出し異常"
            res_ats, sw1, sw2 = conn.transmit(GET_DATA_ATS_APDU)
            status_ats = "読み出し正常" if (sw1 == 0x90 and sw2 == 0x00) else "読み出し異常"
            print(f"IDm : {toHexString(res_uid)} ({status_uid})")
            print(f"PMm : {toHexString(res_ats)} ({status_ats})")

        elif ss == 0x03:
            # MIFARE 判定と表示
            print("Type: MIFARE (Validated, ss=03)")
            card_name = MIFARE_TYPES.get(c0c1_str, "Unknown MIFARE Variant")
            print(f"Card Name (c0:c1) = {c0c1_str} ({card_name})")

            res_uid, sw1, sw2 = conn.transmit(GET_DATA_UID_APDU)
            status_uid = "読み出し正常" if (sw1 == 0x90 and sw2 == 0x00) else "読み出し異常"
            print(f"UID : {toHexString(res_uid)} ({status_uid})")

        else:
            print(f"Error: 未対応のSS値です ({hex(ss)})")
            return

    except Exception as e:
        print(f"Exception: {e}")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
