# /usr/bin/env python2
# coding: utf_8

import os
import time
import sys
if sys.version_info[0] == 2:
    # Pyhton 2
    import urllib2
else:
    # Python 3
    import requests
import datetime

# === Debug Message Flag ===
DEBUG = False  # if "True", message stdout. if "False", no message for cron exec

# === Setting ===
station_id = "62078"        # AMEDAS Station No (example: 44132 for Tokyo, 62078 for Osaka)
save_dir = "~/web/amedas_cron"  # directory
save_filename = "amedas.json"

# === make directory for json datafile ===
if not os.path.exists(save_dir):
    os.makedirs(save_dir)


def get_latest_url_and_filename(station_id):
    """ return AMEDAS json URL and file save local path Strings

    気象庁WebのアメダスデータJSONファイルへのURLと、
    それを保存するためのローカルファイルパス文字列を作成して返す

    :param Str station_id (AMEDAS station No アメダス観測地点No)
    :return Str url, Str local_filepath (気象庁Web json URL, 保存先フルパス名)
    """
    now = datetime.datetime.now()
    yyyymmdd = now.strftime("%Y%m%d")
    h3 = (now.hour // 3) * 3
    h3_str = "%02d" % h3

    url = "https://www.jma.go.jp/bosai/amedas/data/point/%s/%s_%s.json" % (
        station_id, yyyymmdd, h3_str)
    local_filepath = os.path.join(save_dir, save_filename)
    return url, local_filepath


def download_and_save():
    """ download AMEDAS json datafile from JMA web, and save on local_filepath

    気象庁WebからアメダスデータJSONファイルをダウンロードし、
    ローカルディスクに保存する
    """

    url, filepath = get_latest_url_and_filename(station_id)

    if sys.version_info[0] == 2:
        # Python 2の場合はurllib2でHTTPアクセス
        try:
            # OpenSSL バージョンが古く、証明書の検証が正しく行えないため、証明書検証を無効化
            import ssl
            context = ssl._create_unverified_context()
            response = urllib2.urlopen(url, context=context, timeout=5)
            # 通常は次のようにアクセスする（証明書を検証する）
            # response = urllib2.urlopen(url, timeout=5)
            content = response.read()
            if content:
                with open(filepath, "wb") as f:
                    f.write(content)
                if DEBUG:
                    print("save success : %s" % os.path.basename(filepath))
            else:
                if DEBUG:
                    print("fail (JSON file size is 0) : %s" % url)
        except urllib2.HTTPError as e:
            if DEBUG:
                print("HTTP error (%s) : %s" % (e.code, url))
        except urllib2.URLError as e:
            if DEBUG:
                print("Network error : %s" % str(e.reason))
        except Exception as e:
            if DEBUG:
                print("Error : %s" % str(e))
    else:
        # Python 3の場合はrequestsでHTTPアクセス
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print("save success : %s" % os.path.basename(filepath))
            else:
                print("HTTP error (%s) : %s" % (response.status_code, url))
        except Exception as e:
            print("Network error : %s" % str(e))


# === メインループ ===
if __name__ == "__main__":
    if DEBUG:
        print("Download latest AMEDAS Json data from JMA web,"
              " and save it on local filesystem\n"
              "気象庁Webから最新のAMEDAS JSONデータをダウンロードし、ディスク保存する")
    download_and_save()
