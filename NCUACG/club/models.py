# NCUACG/club/models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Course(models.Model):
    """
    成果牆左側的一個分類，例如「114上CM」「113下CM照片」。
    上面還有一層 category（社課種類），對應社課介紹頁六角格的 url。
    """

    CATEGORY_CHOICES = [
        ("anime", "動畫播放組"),
        ("otaku", "御宅藝"),
        ("model", "模型製作"),
        ("art", "繪畫"),
        ("trpg", "TRPG"),
        ("mv", "MV剪輯"),
        ("seiyuu", "聲優"),
        ("railway", "鐵道"),
    ]
    COLOR_CHOICES = [
        ("blue", "藍"),
        ("green", "綠"),
    ]

    # 前端用來辨識課程的 id，例如 114-upper
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="seiyuu", db_index=True)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default="blue")
    # 左側列表的顯示順序，數字小的在上面
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "order", "id"]
        verbose_name = "社課"
        verbose_name_plural = "社課"

    def __str__(self) -> str:
        return f"[{self.get_category_display()}] {self.name}"


class Work(models.Model):
    """成果牆上的一件作品（影片或圖片）。"""

    TYPE_CHOICES = [
        ("video", "影片"),
        ("image", "圖片"),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="works")
    title = models.CharField(max_length=200)
    # 顯示用的作者名稱，例如「113CM組」；不一定是站上的帳號
    author = models.CharField(max_length=100, blank=True)
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="video")

    # 兩種來源擇一：直接上傳到站上，或是放在外部的直連網址
    media_file = models.FileField(upload_to="works/%Y/%m/", blank=True)
    external_url = models.URLField(blank=True)
    thumbnail = models.ImageField(upload_to="works/thumbs/%Y/%m/", blank=True)

    views = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["course", "is_published", "created_at"])]
        verbose_name = "作品"
        verbose_name_plural = "作品"

    def __str__(self) -> str:
        return f"{self.title}（{self.course.name}）"

    def clean(self):
        if not self.media_file and not self.external_url:
            raise ValidationError("請上傳檔案，或填入外部網址（兩者擇一）。")

    @property
    def media_url(self) -> str:
        if self.media_file:
            return self.media_file.url
        return self.external_url


class WorkLike(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["work", "user"], name="unique_work_like"),
        ]


class Comment(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_comments")
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "留言"
        verbose_name_plural = "留言"

    def __str__(self) -> str:
        return f"{self.user.name}：{self.content[:20]}"


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="unique_comment_like"),
        ]


# ── 社課堂次與公告 ───────────────────────────────────────────────────────────

class CourseLead(models.Model):
    """社課負責人：每個社課種類固定指定幾個人（不一定是幹部），只能發、改自己社課的公告。"""

    category = models.CharField("社課", max_length=20, choices=Course.CATEGORY_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_leads", verbose_name="負責人"
    )

    class Meta:
        ordering = ["category", "id"]
        constraints = [
            models.UniqueConstraint(fields=["category", "user"], name="unique_course_lead"),
        ]
        verbose_name = "社課負責人"
        verbose_name_plural = "社課負責人"

    def __str__(self) -> str:
        return f"{self.get_category_display()}：{self.user.name}"


class Lesson(models.Model):
    """
    一堂社課。同一份資料用在 Discord 公告、社課介紹頁、首頁公告欄與行事曆。
    課後負責人可以補上簡報連結，學期末就是一份社課紀錄。
    """

    category = models.CharField("社課", max_length=20, choices=Course.CATEGORY_CHOICES, db_index=True)
    number = models.PositiveIntegerField("第幾堂", null=True, blank=True)
    title = models.CharField("主題", max_length=100, help_text="Discord 公告的「內容：」那一行，例如「高鐵與捷運」")
    start_time = models.DateTimeField("開始時間", db_index=True)
    end_time = models.DateTimeField("結束時間", null=True, blank=True)
    location = models.CharField("地點", max_length=100, default="社辦")
    content = models.TextField("內容介紹", blank=True)
    notes = models.TextField("備註", blank=True, help_text="公告分隔線下面的話，例如「負責人在準備段考……」")
    prerequisites = models.TextField("建議具備", blank=True, help_text="一行一項")
    requires = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="required_by", verbose_name="建議先參加的堂次"
    )
    discord_role = models.CharField("Discord 身分組", max_length=50, blank=True, help_text="例如 @鐵道社課通知")
    slides_url = models.URLField("簡報連結", blank=True)
    is_published = models.BooleanField("公開", default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lessons_created", verbose_name="建立者",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time", "id"]
        indexes = [models.Index(fields=["is_published", "start_time"])]
        verbose_name = "社課堂次"
        verbose_name_plural = "社課堂次"

    def __str__(self) -> str:
        return f"[{self.get_category_display()}] {self.title}"

    def clean(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValidationError({"end_time": "結束時間不能早於開始時間。"})
