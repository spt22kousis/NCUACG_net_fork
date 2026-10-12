# NCUACG/songfest/models.py
"""
歌謠祭資料。

舊曲（Track）與播放紀錄（Play）以社團的 Google 試算表為正本：
「中央動畫社線上歌單」與「最新播放曲目統計」。網站不直接修改這兩種資料，
要改請改試算表，再到後台「匯入試算表」或執行 `python manage.py import_songfest`。
"""
from __future__ import annotations

from django.db import models

from .text import normalize, song_key


class Festival(models.Model):
    """一場歌謠祭。過去的場次在匯入播放紀錄時自動建立，之後的場次由幹部在後台新增。"""

    KIND_CHOICES = [
        ("hall", "大講堂（排歌單）"),
        ("ktv", "KTV（當天點歌）"),
    ]

    name = models.CharField("名稱", max_length=50, help_text="例如 115上期末")
    date = models.DateField("日期", unique=True)
    kind = models.CharField("形式", max_length=10, choices=KIND_CHOICES, default="hall")
    venue = models.CharField("地點", max_length=100, blank=True)
    start_time = models.TimeField("開始時間", null=True, blank=True)
    end_time = models.TimeField("結束時間", null=True, blank=True)
    description = models.TextField("說明", blank=True, help_text="顯示在歌謠祭首頁的公告文字")
    is_published = models.BooleanField("公開", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "歌謠祭場次"
        verbose_name_plural = "歌謠祭場次"

    def __str__(self) -> str:
        return f"{self.name}（{self.date:%Y/%m/%d}）"


class Track(models.Model):
    """歌單裡的一支影片（舊曲），對應線上歌單的一列，以 DVD 編號識別。"""

    dvd_code = models.CharField("DVD 編號", max_length=10, unique=True)
    song_source = models.CharField("歌曲出處", max_length=255)
    visual_source = models.CharField("畫面出處", max_length=255, blank=True)
    title = models.CharField("曲名", max_length=255)
    artist = models.CharField("歌手", max_length=255, blank=True)
    editor = models.CharField("製作者", max_length=100, blank=True)
    duration_seconds = models.PositiveIntegerField("長度（秒）", null=True, blank=True)

    # 線上歌單的五十音分頁：label 是小節（あ、い…或一般曲、特攝），group 是同一行（あ行包含あいうえお）。
    # 作品名大多是漢字，程式排不出五十音順，所以照試算表裡人工排好的順序存 index_order。
    index_label = models.CharField("分類", max_length=20, blank=True)
    index_group = models.CharField("分類（行）", max_length=20, blank=True, db_index=True)
    index_order = models.PositiveIntegerField("排列順序", default=0)

    # 以下由 fill_derived() 算出來，不要手動改
    dvd_sort = models.PositiveIntegerField(default=0, editable=False)
    song_key = models.CharField(max_length=255, db_index=True, editable=False)
    search_text = models.TextField(editable=False, default="")

    class Meta:
        ordering = ["index_order", "dvd_sort"]
        verbose_name = "舊曲"
        verbose_name_plural = "舊曲（歌單）"

    def __str__(self) -> str:
        return f"{self.dvd_code} {self.song_source} - {self.title}"

    def fill_derived(self) -> None:
        """
        算出排序、比對、搜尋用的欄位。匯入時用 bulk_create / bulk_update 不會經過 save()，
        所以匯入程式也要呼叫這個。
        """
        # D0101 是第 1 片 DVD 第 1 首、D13720 是第 137 片第 20 首；用數字比才不會讓 D9921 排在 D10001 後面
        digits = self.dvd_code[1:]
        self.dvd_sort = int(digits) if digits.isdigit() else 0
        self.song_key = song_key(self.song_source, self.title)
        self.search_text = normalize(
            " ".join([self.dvd_code, self.song_source, self.visual_source, self.title, self.artist, self.editor])
        )

    def save(self, *args, **kwargs):
        self.fill_derived()
        super().save(*args, **kwargs)


class Play(models.Model):
    """播放紀錄的一列：某一場歌謠祭播過的一首歌。"""

    # 歌謠祭最後播的 Credits 影片（5 秒畫面合輯）在播放紀錄裡記成這個畫面出處。
    # 它每場都會播，不算排歌組選的歌，所以不計入播放次數與排行榜。
    CREDITS_VISUAL = "5秒畫面"

    MATCH_CHOICES = [
        ("matched", "已對到歌單"),
        ("ambiguous", "有多個版本，無法判斷"),
        ("unmatched", "歌單裡找不到"),
    ]

    festival = models.ForeignKey(Festival, on_delete=models.CASCADE, related_name="plays", verbose_name="場次")
    position = models.PositiveIntegerField("順序", help_text="在播放紀錄試算表中的先後")
    song_source = models.CharField("歌曲出處", max_length=255)
    visual_source = models.CharField("畫面出處", max_length=255, blank=True)
    title = models.CharField("曲名", max_length=255)
    song_key = models.CharField(max_length=255, db_index=True, editable=False)

    # 播放紀錄沒有 DVD 編號，只能用「歌曲出處 + 畫面出處 + 曲名」去對歌單；剛好對到一支才填 track
    track = models.ForeignKey(
        Track, on_delete=models.SET_NULL, null=True, blank=True, related_name="plays", verbose_name="對應舊曲"
    )
    match_status = models.CharField("對應狀態", max_length=10, choices=MATCH_CHOICES, default="unmatched")

    class Meta:
        ordering = ["festival", "position"]
        verbose_name = "播放紀錄"
        verbose_name_plural = "播放紀錄"

    def __str__(self) -> str:
        return f"{self.festival.name} #{self.position} {self.title}"

    def save(self, *args, **kwargs):
        self.song_key = song_key(self.song_source, self.title)
        super().save(*args, **kwargs)
