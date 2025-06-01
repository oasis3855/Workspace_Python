#!/usr/bin/env python
# -*- coding: utf-8 -*-

# permission mode 755 or 705
# このスクリプトは Python 2/3 共用

import os
import sys
if sys.version_info[0] < 3:
    # Python 2
    import cgi
    import urllib
    import urlparse
else:
    # Python 3
    import html
    import urllib.parse

print("Content-Type: text/html; charset=utf-8\n\n")
print("<html>\n <head>\n  <meta charset='utf-8'>\n </head>\n <body>")
print("  <p>こんにちは、世界！</p>")

# Pythonバージョンを表示する
print("  <p>Python Version : {}</p>".format(sys.version_info[0]))
# User-Agent と Accept Language を表示する
user_agent = os.environ.get("HTTP_USER_AGENT", "不明")
accept_language = os.environ.get("HTTP_ACCEPT_LANGUAGE", "不明")
print("  <p>User-Agent : {0}<br/>Accept Language : {1}</p>".format(user_agent, accept_language))
# アクセス側の REMOTE_ADDRESS, REMOTE_HOST を表示する
remote_address = os.environ.get("REMOTE_ADDR", "不明")
remote_host = os.environ.get("REMOTE_HOST", "不明")
print("  <p>Remote Address : {0}<br/>Remote Host : {1}</p>".format(remote_address, remote_host))

# URL-Parameter (GET) を表示する
print("  <p>URLパラメータ</p>")
print("  <ul>")
if not __debug__:   # Debug Switch (-O) : Enabled
    query_string = "param1=val1&param2=val2"    # デバッグ用にサンプルパラメータを代入
else:               # Debug Switch (-O) : Disabled
    query_string = os.environ.get("QUERY_STRING", "QUERY_STRINGなし")
if sys.version_info[0] < 3:
    # Python 2
    params = urlparse.parse_qs(query_string)
else:
    # Python 3
    params = urllib.parse.parse_qs(query_string)
for key, values in params.items():
    if sys.version_info[0] < 3:
        # Python 2
        # URLエンコードをもとに戻す
        decoded_value = urllib.unquote(values[0]) if values[0] else "不明"
        # 特殊文字をエスケープする
        sanitized_value = cgi.escape(decoded_value) if decoded_value else "不明"
        print("    <li>{} : {}</li>".format(cgi.escape(key), sanitized_value))
    else:
        # Python 3
        decoded_value = urllib.parse.unquote(values[0]) if values[0] else "不明"
        sanitized_value = html.escape(decoded_value) if decoded_value else "不明"
        print("    <li>{} : {}</li>".format(html.escape(key), sanitized_value))
# Python 2 で cgiモジュールを使ってURL-Parameterを処理する場合
#url_parmeter = cgi.FieldStorage()
#for key in url_parmeter.keys():
#    value = url_parmeter.getvalue(key)
#    print("<li>{} : {}</li>".format(cgi.escape(key), cgi.escape(value)))
print("  </ul>")

# POSTデータを受信・表示する（`wsgi.input`を使用）
print("  <p>POSTデータ</p>")
print("  <ul>")
content_length = int(os.environ.get("CONTENT_LENGTH", 0))
if not __debug__:   # Debug Switch (-O) : Enabled
    content_length = len("param1=val1&param2=val2") # デバッグ用にサンプルパラメータを代入
if content_length > 0:
    if not __debug__:   # Debug Switch (-O) : Enabled
        query_string = "param1=val1&param2=val2"    # デバッグ用にサンプルパラメータを代入
    else:
        query_string = sys.stdin.read(content_length)  # `sys.stdin.read()` で生のPOSTデータを取得
    if sys.version_info[0] < 3:
        # Python 2
        params = urlparse.parse_qs(query_string)
    else:
        # Python 3
        params = urllib.parse.parse_qs(query_string)
    for key, values in params.items():
        if sys.version_info[0] < 3:
            # Python 2
            # URLエンコードをもとに戻す
            decoded_value = urllib.unquote(values[0]) if values[0] else "不明"
            # 特殊文字をエスケープする
            sanitized_value = cgi.escape(decoded_value) if decoded_value else "不明"
            print("    <li>{} : {}</li>".format(cgi.escape(key), sanitized_value))
        else:
            # Python 3
            decoded_value = urllib.parse.unquote(values[0]) if values[0] else "不明"
            sanitized_value = html.escape(decoded_value) if decoded_value else "不明"
            print("    <li>{} : {}</li>".format(html.escape(key), sanitized_value))
print("  </ul>")

print(" </body>\n</html>")
