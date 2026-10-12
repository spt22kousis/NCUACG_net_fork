# NCUACG/songfest/text.py
"""
試算表文字的整理與比對。

歌單、播放紀錄都是人工打字，同一首歌常常有全形半形、大小寫、空白、標點的差異，
例如「ラブライブ!」和「ラブライブ！」。比對和搜尋前一律先經過 normalize()。
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata


def normalize(value: str) -> str:
    """
    比對用的字串：NFKC（全形轉半形）、不分大小寫、只留文字和數字。
    整串都是符號時（例如曲名就叫「!!」），退回只做 NFKC 與大小寫，避免變成空字串。
    """
    text = unicodedata.normalize("NFKC", value or "").casefold()
    kept = "".join(ch for ch in text if unicodedata.category(ch)[0] in "LN")
    return kept or text.strip()


def song_key(song_source: str, title: str) -> str:
    """
    「同一首歌」的判斷依據：歌曲出處 + 曲名。
    同一首歌可能有好幾個人剪的版本（不同 DVD 編號、不同畫面），
    播放次數、上次播放都照排歌組的習慣以「歌」為單位計算，不分版本。
    """
    return f"{normalize(song_source)}|{normalize(title)}"[:255]


def cell_text(value) -> str:
    """
    把試算表儲存格轉成文字。Google 試算表匯出時會把一些曲名、製作者轉成別的型別：
    曲名「TRUE」變成布林值、曲名「65535」與製作者「300」變成浮點數。
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


_DURATION_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")


def duration_seconds(value) -> int | None:
    """長度欄位轉成秒數。試算表裡可能是時間、時間差、「4:25」這種文字，或 Excel 的「一天的幾分之幾」。"""
    if value is None or value == "":
        return None
    if isinstance(value, dt.time):
        return value.hour * 3600 + value.minute * 60 + value.second
    if isinstance(value, dt.timedelta):
        return int(value.total_seconds())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # 小於 1 視為 Excel 的時間（一天 = 1.0）
        return round(value * 86400) if 0 < value < 1 else None
    match = _DURATION_RE.match(str(value).strip())
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    return None


def play_date(value) -> dt.date | None:
    """播放日期欄是 20260614 這種數字，也接受日期型別與「2026/06/14」文字。"""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = cell_text(value).replace("/", "").replace("-", "")
    if len(text) == 8 and text.isdigit():
        try:
            return dt.date(int(text[:4]), int(text[4:6]), int(text[6:]))
        except ValueError:
            return None
    return None


def guess_festival_name(date: dt.date) -> str:
    """
    從日期推場次名稱，例如 2026/06/14 → 114下期末。只在匯入時建立新場次用，之後可以在後台改名。
    學年度從 8 月開始；上學期 8–10 月算期初、11–1 月算期末，下學期 2–4 月期初、5–7 月期末。
    （KTV 期中場不在播放紀錄裡，所以這裡不會出現期中。）
    """
    roc_year = date.year - 1911 if date.month >= 8 else date.year - 1912
    if date.month >= 8 or date.month == 1:
        semester, term = "上", "期初" if 8 <= date.month <= 10 else "期末"
    else:
        semester, term = "下", "期初" if date.month <= 4 else "期末"
    return f"{roc_year}{semester}{term}"
