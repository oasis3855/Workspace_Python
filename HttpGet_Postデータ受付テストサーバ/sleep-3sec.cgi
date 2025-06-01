#!/usr/bin/env python
# -*- coding: utf-8 -*-

# permission mode 755 or 705
# このスクリプトは Python 2/3 共用

import sys
import time

print("Content-Type: text/html; charset=utf-8\n\n")
print("<html>\n <head>\n  <meta charset='utf-8'>\n </head>\n <body>")
print("  <p>こんにちは、世界！</p>")
# Pythonバージョンを表示する
print("  <p>Python Version : {}</p>".format(sys.version_info[0]))

print("  <p>ここで3秒ディレイが入ります</p>")
# 3秒のディレイ
time.sleep(3)

print("  <p>さようなら、世界！</p>")
print(" </body>\n</html>")
