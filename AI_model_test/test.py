import datetime
import sys

def get_and_calculate_date_difference()->None:
    print("--- 日付差計算スクリプト ---")
    print("日付を入力してください (形式: yyyy/mm/dd):")

    while True:
        date_input = input("> ")
        try:
            # 1. 入力のパースと妥当性のチェック
            input_date = datetime.datetime.strptime(date_input, "%Y/%m/%d").date()

            # 2. 日付の妥当性チェック（ここでは単純な範囲チェック）
            today = datetime.date.today()
            if input_date > today:
                print("エラー: 入力された日付は今日よりも未来の日付です。")
                continue
            elif input_date < datetime.date.min:
                print("エラー: 無効な日付が入力されました。")
                continue
            else:
                # 3. 日数計算
                delta = today - input_date
                print(f"{today.year:04d}")
                if delta.days < 0:
                    print("エラー: 入力された日付は未来の日付です。")
                    continue
                
                print(f"\n入力された日付: {input_date.strftime('%Y/%m/%d')}")
                print(f"今日との差は {delta.days} 日です。")
                break
                
        except ValueError:
            # 日付形式が間違っている場合
            print("エラー: 日付の形式が正しくありません。'yyyy/mm/dd' 形式で入力してください。")
        except Exception as e:
            # その他の予期せぬエラー
            print(f"予期せぬエラーが発生しました: {e}")


if __name__ == "__main__":
    get_and_calculate_date_difference()
