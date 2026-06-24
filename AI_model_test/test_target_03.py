import requests
from bs4 import BeautifulSoup

# URL を設定します。
STR_URL = "https://oasis3855.github.io/webpage/links/link_simple.html"

try:
    # リクエストを送信し、HTML コードを取得します。
    response = requests.get(STR_URL)

    # HTTP レスポンスが成功していることを確認します。
    response.raise_for_status()

    # HTML コードを BeautifulSoup オブジェクトにパースします。
    
    soup = BeautifulSoup()

    # soup = BeautifulSoup(response.text, 'html.parser')

    # HTML タグを取り除き、プレーンテキストを取得します。
    plain_text = soup.get_text(separator='\n', strip=True)

    # プレーンテキストを画面に出力します。
    print(plain_text)

except requests.exceptions.RequestException as e:
    print(f"リクエスト中にエラーが発生しました: {e}")
