# CSVファイル filename(str) を読み込んで、リストとして返す関数を定義する。
def read_csv(filename):
    # ファイルを開く
    try
        with open(filename, 'r') as f:
            # データを格納する変数を用意する
            data = []
            # ファイルから1行ずつデータを読み込む
            for line in f:
                # 改行文字と空白文字を除去して、リストに追加する
                data.append(line.strip().split(','))
    except FileNotFoundError:
        # ファイルが存在しない場合、エラーメッセージを表示して終了する
        print(f'{filename} not found.')
    except 
    return data
# CSVファイルの名前を指定する
filename = 'data.csv' 
# データを読み込む
data = read_csv(filename) 


def calc_average_and_maxmin(num_list):
    """
    num_list (list of int): 整数のリスト

    Returns:
        tuple: 平均値と最大値、最小値を含むタプル
    """
    # リストが空の場合、Noneを返す
    if not num_list:
        return None, None, None

    # 平均値を計算する
    average = sum(num_list) / len(num_list)

    # 最大値と最小値を計算する
    max_value = max(num_list)
    min_value = min(num_list)

    # 結果をタプルとして返す
    return average, max_value, min_value
# データから整数のリストを作成する
num_list = [int(x) for x in data[0] if x.isdigit()]
# 平均値と最大値、最小値を計算して出力する
average, max_value, min_value = calc_average_and_maxmin(num_list)
print(f'平均値: {average}')
print(f'最大値: {max_value}')
print(f'最小値: {min_value}')



# 引数aとbの和を返す
def add_a_b(a,b):
    


# 1から100の間の素数のリストを返す関数を定義する
def get_primes_in_range(start, end):