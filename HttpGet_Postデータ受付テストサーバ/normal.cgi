#!/usr/bin/env python
# -*- coding: utf-8 -*-

# permission mode 755 or 705
# このスクリプトは Python 2/3 共用

import os
import sys

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

print(" </body>\n</html>")
