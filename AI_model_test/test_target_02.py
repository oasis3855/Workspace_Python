def hello():
    """
    Hello, World! を表示します。


    """

    print("Hello, World!")

def hello_world():
    print("Hello, World!")

# 文字列 a と、文字列 b の長さを比較し、長い方の文字列の文字数を返す関数






def add(a:int, b:int)->int:
    """
    2つの整数を加えて、その和を返します。

    Parameters:
        a (int): 加算する整数1
        b (int): 加算する整数2

    Returns:
        int: 加算結果
    """

    return a + b




def receive_html(url: str) -> str:
    """
    指定されたURLからHTMLを取得します。

    引数:
        url (str): HTMLを取得するURL

    戻り値:
        str: 取得したHTML内容
    """

    import requests
    try:
        response = requests.get(url)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching HTML: {e}")
        return ""

def receive_html(url: str) -> str:
    """
    指定されたURLからHTMLを取得します。

    引数:
        url (str): HTMLを取得するURL

    戻り値:
        str: 取得したHTML内容
    """

    import requests
    try:
        response = requests.get(url)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching HTML: {e}")
        return ""

