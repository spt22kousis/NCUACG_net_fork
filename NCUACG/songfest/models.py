# NCUACG/songfest/models.py
"""
歌謠祭資料。

舊曲（Track）與播放紀錄（Play）以社團的 Google 試算表為正本：
「中央動畫社線上歌單」與「最新播放曲目統計」。網站不直接修改這兩種資料，
要改請改試算表，再到後台「匯入試算表」或執行 `python manage.py import_songfest`。

新曲投稿（Submission）取代原本的 Google 試算表回報串，直接存在網站上。
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

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

    # 新曲投稿的截止時間（沒填就不開放投稿）。規則見「歌謠祭曲目投稿規則」
    # 社外投稿規則：合作社團的期限跟社內相同，所以只有一個報曲截止
    report_deadline = models.DateTimeField("報曲截止", null=True, blank=True)
    withdraw_deadline = models.DateTimeField(
        "窗歌截止", null=True, blank=True, help_text="過了這個時間才窗歌，下次歌謠祭禁止報曲 1 次"
    )
    upload_deadline = models.DateTimeField(
        "新曲與 5 秒畫面繳交截止", null=True, blank=True, help_text="沒上傳視同逾期窗歌；5 秒畫面沒上傳視為不放"
    )
    partner_name = models.CharField("合作社團", max_length=50, default="健行科大")
    partner_limit = models.PositiveSmallIntegerField("合作社團新曲上限", default=10)
    rules = models.TextField("出曲規定", blank=True, help_text="顯示在新曲投稿頁")

    # 亂入曲用 Google 表單收，網站只顯示說明與連結，表單回覆再由排歌組匯入
    guest_deadline = models.DateTimeField("亂入曲截止", null=True, blank=True)
    guest_form_url = models.URLField("亂入曲 Google 表單網址", blank=True)
    guest_info = models.TextField("亂入投稿說明", blank=True, help_text="顯示在亂入投稿說明頁")

    # 排歌台排好的歌單要不要公開在「歌單瀏覽」（通常是活動當天或前一天公布）
    setlist_public = models.BooleanField("公開排好的歌單", default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "歌謠祭場次"
        verbose_name_plural = "歌謠祭場次"

    def __str__(self) -> str:
        return f"{self.name}（{self.date:%Y/%m/%d}）"

    def report_deadline_for(self, source: str):
        if source == "guest":
            return self.guest_deadline
        return self.report_deadline

    def is_report_open(self, source: str, now=None) -> bool:
        """這場現在還能不能報曲（亂入曲走 Google 表單，網站上一律不能報）。"""
        deadline = self.report_deadline_for(source)
        now = now or timezone.now()
        return self.kind == "hall" and source != "guest" and deadline is not None and now <= deadline

    def previous_hall_festival(self):
        """上一場大講堂歌謠祭：罰則「下次歌謠祭禁止報曲」與「上一場播過」都以它為準。"""
        return Festival.objects.filter(kind="hall", date__lt=self.date).order_by("-date").first()

    @classmethod
    def active(cls):
        """目前在準備的那一場：今天以後最近的大講堂歌謠祭。"""
        return (
            cls.objects.filter(kind="hall", is_published=True, date__gte=timezone.localdate())
            .order_by("date")
            .first()
        )


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


class FestivalStaff(models.Model):
    """一場歌謠祭的排歌組成員。新人也能擔任，所以不綁「幹部」身分。"""

    ROLE_CHOICES = [
        ("lead", "主排"),
        ("credits", "抄歌"),
        ("player", "播歌"),
    ]

    festival = models.ForeignKey(Festival, on_delete=models.CASCADE, related_name="staff", verbose_name="場次")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="songfest_staff", verbose_name="帳號"
    )
    role = models.CharField("職位", max_length=10, choices=ROLE_CHOICES)

    class Meta:
        verbose_name = "排歌組成員"
        verbose_name_plural = "排歌組成員"
        constraints = [models.UniqueConstraint(fields=["festival", "user"], name="unique_festival_staff")]

    def __str__(self) -> str:
        return f"{self.festival.name} {self.get_role_display()} {self.user.name}"


class Submission(models.Model):
    """
    一首新曲投稿，對應原本回報串的一列。
    社內、合作社團在網站上報曲；亂入曲由排歌組匯入 Google 表單的回覆。
    """

    SOURCE_CHOICES = [
        ("member", "社內"),
        ("partner", "合作社團"),
        ("guest", "亂入"),
    ]
    STATUS_LABELS = {
        "reported": "已報曲",
        "uploaded": "已繳交",
        "overdue": "逾期未繳交",
        "withdrawn": "窗歌",
        "rejected": "退件",
    }
    # 連曲：至多 2 首、總長不超過 10 分鐘
    CHAIN_MAX_SECONDS = 600

    festival = models.ForeignKey(Festival, on_delete=models.CASCADE, related_name="submissions", verbose_name="場次")
    source = models.CharField("來源", max_length=10, choices=SOURCE_CHOICES, default="member")
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="songfest_submissions", verbose_name="投稿帳號",
    )
    editor_name = models.CharField("製作者", max_length=100)
    contact_email = models.EmailField("聯絡信箱", blank=True, help_text="亂入曲投稿人的信箱，只有排歌組看得到")

    # 回報串欄位
    song_source = models.CharField("歌曲出處", max_length=255, help_text="ACGN 歌曲填作品名稱；非 ACGN 填「一般曲」")
    visual_source = models.CharField("畫面出處", max_length=255, help_text="多部作品或非 ACGN 畫面填「複數作品」")
    title = models.CharField("曲名", max_length=255)
    artist = models.CharField("原唱歌手", max_length=255, blank=True)
    attributes = models.TextField("畫面或作品屬性", blank=True, help_text="簡述畫面素材或作品性質，自製畫面也要註明")
    song_link = models.CharField("歌曲連結", max_length=500, blank=True, help_text="使用歌曲的連結，自製歌曲也要註明")
    remarks = models.TextField("備註", blank=True, help_text="畫面素材、歌曲、剪輯手法；難界定的內容務必註明")
    restricted_work = models.BooleanField("作品有公告禁止二創或限制", default=False)
    five_sec = models.BooleanField("要上傳 5 秒畫面", default=False)
    is_backup = models.BooleanField(
        "備曲", default=False, help_text="合作社團的備用曲：正選未滿上限時才補上，不算進上限"
    )
    chain_with = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="連曲", help_text="想跟自己的哪一首連續播出",
    )

    # 繳交
    file_link = models.CharField("檔案連結", max_length=500, blank=True)
    duration_seconds = models.PositiveIntegerField("長度（秒）", null=True, blank=True)
    uploaded_at = models.DateTimeField("繳交時間", null=True, blank=True)
    file_updated_at = models.DateTimeField("檔案最後修改", null=True, blank=True)
    five_sec_link = models.CharField("5 秒畫面連結", max_length=500, blank=True)
    five_sec_uploaded_at = models.DateTimeField("5 秒畫面繳交時間", null=True, blank=True)

    # 狀態與排歌組處理
    withdrawn_at = models.DateTimeField("窗歌時間", null=True, blank=True)
    extended_until = models.DateTimeField("延後繳交到", null=True, blank=True)
    file_checked = models.BooleanField("排歌組已確認檔案", default=False)
    is_rejected = models.BooleanField("退件", default=False)
    reject_reason = models.CharField("退件原因", max_length=200, blank=True)
    penalty_waived = models.BooleanField("免除罰則", default=False)

    # 亂入曲表單的其他欄位
    library_consent = models.BooleanField("同意收進社團歌單", default=False)
    guest_message = models.TextField("想對我們說的話", blank=True)
    external_id = models.CharField("表單回覆識別碼", max_length=200, blank=True, db_index=True, editable=False)
    # 活動結束後收進社團歌單，變成舊曲
    track = models.ForeignKey(
        "Track", on_delete=models.SET_NULL, null=True, blank=True, related_name="submissions",
        verbose_name="收進歌單後的舊曲",
    )

    song_key = models.CharField(max_length=255, db_index=True, editable=False)
    created_at = models.DateTimeField("報曲時間", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "新曲投稿"
        verbose_name_plural = "新曲投稿"

    def __str__(self) -> str:
        return f"{self.festival.name} {self.editor_name}〈{self.title}〉"

    def save(self, *args, **kwargs):
        self.song_key = song_key(self.song_source, self.title)
        super().save(*args, **kwargs)

    # ── 狀態判斷（都跟「現在幾點」有關，所以不存進資料庫）──

    @property
    def upload_deadline(self):
        return self.extended_until or self.festival.upload_deadline

    @property
    def is_active(self) -> bool:
        """還在出曲名單上（沒窗歌、沒退件）"""
        return self.withdrawn_at is None and not self.is_rejected

    @property
    def is_uploaded(self) -> bool:
        return self.uploaded_at is not None and bool(self.file_link)

    @property
    def changed_after_upload(self) -> bool:
        """繳交後又改了檔案或長度：規則要求通知排歌組，這裡直接標給排歌組看"""
        return bool(self.uploaded_at and self.file_updated_at and self.file_updated_at > self.uploaded_at)

    def status(self, now=None) -> str:
        now = now or timezone.now()
        if self.is_rejected:
            return "rejected"
        if self.withdrawn_at:
            return "withdrawn"
        if self.is_uploaded:
            return "uploaded"
        deadline = self.upload_deadline
        if deadline and now > deadline:
            return "overdue"
        return "reported"

    def withdraw_is_late(self, when=None) -> bool:
        deadline = self.festival.withdraw_deadline
        return bool(deadline and (when or timezone.now()) > deadline)

    def is_offense(self, now=None) -> bool:
        """
        會被記罰則（下次歌謠祭禁止報曲 1 次）：過了窗歌截止才窗歌，或過了繳交截止還沒上傳。
        亂入曲不適用；排歌組可以免除。
        """
        if self.source == "guest" or self.penalty_waived or self.is_rejected:
            return False
        if self.withdrawn_at:
            return self.withdraw_is_late(self.withdrawn_at)
        return self.status(now) == "overdue"

    def five_sec_status(self, now=None) -> str:
        """none 不放、pending 待繳、uploaded 已繳、cancelled 取消（歌曲窗掉或逾期，5 秒畫面也跟著取消）"""
        if not self.five_sec:
            return "none"
        if self.status(now) in ("withdrawn", "rejected", "overdue"):
            return "cancelled"
        if self.five_sec_uploaded_at and self.five_sec_link:
            return "uploaded"
        deadline = self.upload_deadline
        if deadline and (now or timezone.now()) > deadline:
            return "cancelled"
        return "pending"


class SubmissionComment(models.Model):
    """回報串的「閒聊」：每首投稿底下的留言。"""

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="songfest_comments"
    )
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "回報串留言"
        verbose_name_plural = "回報串留言"

    def __str__(self) -> str:
        return f"{self.user.name}：{self.content[:20]}"


class Session(models.Model):
    """
    一場歌謠祭裡的一個時段：測試曲、上午場、下午一、下午二。
    預設值照排歌組工作區（見 setlist.DEFAULT_SESSIONS），通常不用改。
    """

    festival = models.ForeignKey(Festival, on_delete=models.CASCADE, related_name="sessions", verbose_name="場次")
    name = models.CharField("名稱", max_length=20)
    order = models.PositiveSmallIntegerField("順序", default=0)
    is_test = models.BooleanField("測試曲", default=False, help_text="開場前輪播，不算進正式歌單")
    start_time = models.TimeField("開播時刻")
    end_time = models.TimeField("結束時刻", null=True, blank=True)
    target_seconds = models.PositiveIntegerField("目標長度（秒）", null=True, blank=True)
    tolerance_seconds = models.PositiveIntegerField("可超過（秒）", default=120)
    speech_seconds = models.PositiveIntegerField("內場負責人講話（秒）", default=60)
    buffer_seconds = models.PositiveIntegerField("預留錯誤處理（秒）", default=240)
    per_song_error_seconds = models.PositiveSmallIntegerField("PotPlayer 每首誤差（秒）", default=1)
    rounds = models.PositiveSmallIntegerField("輪數", default=1, help_text="測試曲重複播放幾輪")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="songfest_sessions", verbose_name="負責排歌",
    )

    class Meta:
        ordering = ["festival", "order", "id"]
        verbose_name = "歌單時段"
        verbose_name_plural = "歌單時段"

    def __str__(self) -> str:
        return f"{self.festival.name} {self.name}"


class SetlistEntry(models.Model):
    """時段裡的一首：這次的新曲、歌單裡的舊曲，或自己填的項目（CM、結尾影片、社外舊曲…）。"""

    KIND_CHOICES = [
        ("new", "新曲"),
        ("old", "舊曲"),
        ("custom", "其他"),
    ]
    CUSTOM_TYPE_CHOICES = [
        ("cm", "CM"),
        ("credits", "結尾影片"),
        ("other", "其他"),
    ]

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="entries", verbose_name="時段")
    position = models.PositiveIntegerField("順序")
    kind = models.CharField("種類", max_length=10, choices=KIND_CHOICES)
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, null=True, blank=True, related_name="setlist_entries"
    )
    track = models.ForeignKey(Track, on_delete=models.PROTECT, null=True, blank=True, related_name="setlist_entries")
    custom_type = models.CharField("其他項目類型", max_length=10, choices=CUSTOM_TYPE_CHOICES, blank=True)
    custom_title = models.CharField("曲名／名稱", max_length=255, blank=True)
    custom_source = models.CharField("作品", max_length=255, blank=True)
    custom_editor = models.CharField("製作者", max_length=100, blank=True)
    custom_duration = models.PositiveIntegerField("長度（秒）", null=True, blank=True)
    heat = models.PositiveSmallIntegerField("熱度", null=True, blank=True)
    note = models.CharField("備註", max_length=200, blank=True)

    class Meta:
        ordering = ["session", "position", "id"]
        verbose_name = "歌單項目"
        verbose_name_plural = "歌單項目"

    def __str__(self) -> str:
        return f"{self.session} #{self.position} {self.title}"

    @property
    def title(self) -> str:
        if self.kind == "new":
            return self.submission.title
        if self.kind == "old":
            return self.track.title
        return self.custom_title

    @property
    def song_source(self) -> str:
        if self.kind == "new":
            return self.submission.song_source
        if self.kind == "old":
            return self.track.song_source
        return self.custom_source

    @property
    def visual_source(self) -> str:
        if self.kind == "new":
            return self.submission.visual_source
        if self.kind == "old":
            return self.track.visual_source
        return self.custom_source

    @property
    def editor(self) -> str:
        if self.kind == "new":
            return self.submission.editor_name
        if self.kind == "old":
            return self.track.editor
        return self.custom_editor

    @property
    def duration(self):
        if self.kind == "new":
            return self.submission.duration_seconds
        if self.kind == "old":
            return self.track.duration_seconds
        return self.custom_duration
