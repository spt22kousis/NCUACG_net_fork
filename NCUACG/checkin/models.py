# NCUACG/checkin/models.py
"""
活動簽到：社團自己的出席紀錄（學校的 QR code 時數系統照舊，跟這裡無關）。
掃描頁是 barcoder demo 搬進來的（frontend/public/scan/），掃學生證背面的 Code 128 條碼取得學號。
"""
import secrets

from django.conf import settings
from django.db import models


def new_scan_key() -> str:
    return secrets.token_urlsafe(18)


class CheckinEvent(models.Model):
    """
    一個簽到活動：一場歌謠祭、一堂社課，或自訂的活動（社員大會、社遊…）。
    掃描頁靠 scan_key 寫入紀錄，外場志工不用帳號；連結外流時重設 scan_key 即可。
    """

    title = models.CharField("名稱", max_length=100)
    festival = models.OneToOneField(
        "songfest.Festival", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="checkin_event", verbose_name="歌謠祭場次",
    )
    lesson = models.OneToOneField(
        "club.Lesson", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="checkin_event", verbose_name="社課堂次",
    )
    scan_key = models.CharField("掃描密鑰", max_length=40, default=new_scan_key, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="checkin_events", verbose_name="建立者",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "簽到活動"
        verbose_name_plural = "簽到活動"

    def __str__(self) -> str:
        return self.title

    @property
    def kind(self) -> str:
        return "songfest" if self.festival_id else "lesson" if self.lesson_id else "other"


class CheckinSlot(models.Model):
    """活動裡的一個場次，例如歌謠祭的上午場。只有在 opens_at ～ closes_at 之間掃描才算數。"""

    event = models.ForeignKey(CheckinEvent, on_delete=models.CASCADE, related_name="slots")
    name = models.CharField("場次", max_length=50)
    order = models.PositiveSmallIntegerField(default=0)
    starts_at = models.DateTimeField("開始")
    ends_at = models.DateTimeField("結束")
    opens_at = models.DateTimeField("開放簽到")
    closes_at = models.DateTimeField("停止簽到")

    class Meta:
        ordering = ["event", "order", "starts_at", "id"]
        verbose_name = "簽到場次"
        verbose_name_plural = "簽到場次"

    def __str__(self) -> str:
        return f"{self.event.title}：{self.name}"


class Checkin(models.Model):
    """一筆簽到。同一個場次同一個學號只留第一筆（多台裝置離線時可能各掃到一次）。"""

    SOURCE_CHOICES = [
        ("camera", "鏡頭"),
        ("scanner", "掃描槍"),
        ("manual", "手動"),
    ]

    slot = models.ForeignKey(CheckinSlot, on_delete=models.CASCADE, related_name="checkins")
    student_id = models.CharField("學號", max_length=20, db_index=True)
    raw = models.CharField("原始條碼", max_length=64, blank=True)
    source = models.CharField("來源", max_length=10, choices=SOURCE_CHOICES, default="camera")
    scanned_at = models.DateTimeField("掃描時間", help_text="裝置上的時間；離線補送時跟上傳時間不同")
    received_at = models.DateTimeField("上傳時間", auto_now_add=True)
    # 裝置產生的編號：同一筆紀錄重送（網路不穩時）不會重複寫入
    client_id = models.CharField(max_length=64, unique=True)
    device = models.CharField("裝置", max_length=64, blank=True)

    class Meta:
        ordering = ["scanned_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["slot", "student_id"], name="unique_checkin_per_slot"),
        ]
        verbose_name = "簽到紀錄"
        verbose_name_plural = "簽到紀錄"

    def __str__(self) -> str:
        return f"{self.slot}：{self.student_id}"
