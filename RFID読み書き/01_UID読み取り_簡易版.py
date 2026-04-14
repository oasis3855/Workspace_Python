#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MIFARE/FeliCa カードのUID/ATS(IDm/PMm)を読み取って表示するスクリプト。

Requires:
    - Python 3.x
    - pyscard: スマートカード通信ライブラリ (pip install pyscard)

Author:
    Google Gemini 3 (Collaborative development)

Version:
    1.0.0 (2026/03/27)
"""

from smartcard.util import toHexString
from smartcard.System import readers

# コマンド定義
GET_DATA_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]
GET_DATA_ATS_APDU = [0xFF, 0xCA, 0x01, 0x00, 0x00]


def main():
    print("Read UID/ATS(IDm/PMm) from smart card ( simple version )")

    try:
        reader_list = readers()
    except BaseException:
        print("Error: PCSCサービスが起動していません。")
        return

    if not reader_list:
        print("Error: リーダーが見つかりません。")
        return

    reader = reader_list[0]
    print("利用するRFIDリーダー : " + str(reader).split('[')[0].strip())

    conn = reader.createConnection()

    try:
        conn = reader.createConnection()
        conn.connect()
    except Exception as message:
        print("Exception : " + str(message))
        return

    try:
        RecvApduList, sw1, sw2 = conn.transmit(GET_DATA_UID_APDU)
        status_uid = "読み出し正常" if (sw1 == 0x90 and sw2 == 0x00) else "読み出し異常"
        print(
            f"UID(IDm) = {toHexString(RecvApduList)} ({status_uid}), sw1:sw2 = {sw1:02x} {sw2:02x}")

        RecvApduList, sw1, sw2 = conn.transmit(GET_DATA_ATS_APDU)
        status_ats = "読み出し正常" if (sw1 == 0x90 and sw2 == 0x00) else "読み出し異常"
        print(
            f"ATS(PMm) = {toHexString(RecvApduList)} ({status_ats}), sw1:sw2 = {sw1:02x} {sw2:02x}")

    except Exception as message:
        print("Exception : " + str(message))
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
