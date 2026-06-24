import sys


def print_hello_10times() -> None:
    """
    Summary in Japanese: この関数は10回「Hello」と「Hello 2」を順番に表示します。

    Args:
        None.

    Returns:
        None.
    """

    
    
    
    

    for _ in range(10):
        print("Hello")

    for _ in range(10):
        print("Hello 2")

    
    

def get_user_input() -> str:
    """
    ユーザーからの入力を取得する関数です。
    Returns:
        str: 入力されたテキスト。
    """
    try:
    
        return input("Enter some text: ")
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)


def process_text(text: str) -> str:
    """
    テキストを処理する関数です。

    Args:
        text (str): 処理対象のテキスト。

    Returns:
        str: 処理後のテキスト。
    """
    cleaned = text.strip()
    return f"PROCESSED: {cleaned.upper()}"


def main() -> None:
    """
    メイン関数です。ユーザーからの入力を取得し、処理した結果を出力します。

    Returns:
        None
    """
    raw_data = get_user_input()
    result = process_text(raw_data)
    print(result)


if __name__ == "__main__":
    main()
