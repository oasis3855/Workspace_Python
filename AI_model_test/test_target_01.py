import math

def is_prime(n: int) -> bool:
    # 1以下の数は素数ではない
    if n <= 1:
        return False
    
    # 2は素数
    if n == 2:
        return True
    
    # 偶数は2以外は素数ではない
    if n % 2 == 0:
        return False

    # 3から平方根までの奇数について割り切れるかチェックする
    # 2の倍数をスキップし、効率を向上させる
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
            
    # 割り切れる数がなければ素数である
    return True

def find_primes_in_range(start: int, end: int) -> list[int]:
    """
    指定された範囲内にあるすべての素数をリストとして抽出する。

    Args:
        start (int): 検索を開始する下限値（含む）。
        end (int): 検索を終了する上限値（含む）。

    Returns:
        list[int]: startからendまでの範囲に含まれる素数のリスト。
    """
    prime_numbers: list[int] = []
    # startからendまでのすべての数について素数判定を行う
    for number in range(start, end + 1):
        if is_prime(number):
            prime_numbers.append(number)
    return prime_numbers

def main():
    """
    ユーザーからの入力を受け取り、素数を検索して表示するメイン処理。
    """
    print("--- 素数検索プログラム ---")
    
    while True:
        try:
            # ユーザーから開始値と終了値を入力してもらう
            start_input = input("素数を検索したい範囲の開始値を入力してください (例: 1): ")
            end_input = input("素数を検索したい範囲の終了値を入力してください (例: 100): ")
            
            start = int(start_input)
            end = int(end_input)
            
            if start > end:
                print("エラー: 開始値は終了値以下である必要があります。再度入力してください。")
                continue

            if start < 0:
                 print("エラー: 範囲は0以上の整数で指定してください。")
                 continue

            # 素数を検索
            primes = find_primes_in_range(start, end)

            # 結果の表示
            if primes:
                print(f"\n【結果】{start} から {end} までの素数:")
                # リストをスペース区切りで表示
                print(*(primes))
            else:
                print(f"\n【結果】{start} から {end} の範囲には素数が見つかりませんでした。")

            # ユーザーに再実行するか尋ねる
            another = input("\n再度検索を実行しますか？ (y/n): ").lower()
            if another != 'y':
                break

        except ValueError:
            # 数値以外の入力があった場合の処理
            print("\n入力エラー: 有効な整数を入力してください。")
        except Exception as e:
            # その他の予期せぬエラー処理
            print(f"\n予期せぬエラーが発生しました: {e}")
            break

if __name__ == "__main__":
    main()