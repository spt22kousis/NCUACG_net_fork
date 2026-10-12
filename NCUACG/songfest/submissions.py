# NCUACG/songfest/submissions.py
"""
新曲投稿的規則（對應「歌謠祭曲目投稿規則」）。API 與測試都從這裡呼叫，規則只寫一份。

  - 報曲：截止前可以新增、修改、刪除；不接受兩人報同一首歌（撞曲直接擋下）。
  - 合作社團（社外投稿規則）：正選上限 10 首，未滿時由「備曲」補上；跟社內撞曲時優先保留社內作品。
  - 亂入曲（Google 表單）：每人最多 5 首、5 秒畫面每人最多 5 秒；由排歌組決定入選。
  - 窗歌：報曲截止前直接刪除；截止後標記窗歌。過了窗歌截止才窗歌，下次歌謠祭禁止報曲 1 次。
  - 繳交：填檔案連結與長度就算繳交；過了繳交截止還沒交，視同逾期窗歌（一樣記罰則）。
  - 報曲截止後要換歌、改 5 秒畫面，要找排歌組（後台修改）。
  - 連曲：至多 2 首、總長不超過 10 分鐘。
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import Festival, FestivalStaff, Play, Submission
from .text import normalize, song_key

# 這些「畫面出處」不是單一作品，不拿來判斷撞作品
_GENERIC_VISUALS = {normalize("複數作品"), normalize("一般曲"), normalize("自製畫面"), ""}


# ── 權限 ────────────────────────────────────────────────────────────────────

def is_officer(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def is_staff_for(user, festival: Festival) -> bool:
    """幹部，或是這一場的排歌組成員。"""
    if not (user and user.is_authenticated):
        return False
    return is_officer(user) or FestivalStaff.objects.filter(festival=festival, user=user).exists()


def is_songfest_staff(user) -> bool:
    """側邊欄要不要顯示「管理歌單」：幹部，或是之後某一場的排歌組成員。"""
    if not (user and user.is_authenticated):
        return False
    return is_officer(user) or FestivalStaff.objects.filter(
        user=user, festival__date__gte=timezone.localdate()
    ).exists()


def ban_reason(user, festival: Festival, now=None) -> str | None:
    """上一場歌謠祭逾期窗歌（或逾期沒交）的人，這一場不能報曲。回傳原因，沒有被禁就回 None。"""
    previous = festival.previous_hall_festival()
    if previous is None or not (user and user.is_authenticated):
        return None
    for sub in previous.submissions.filter(submitter=user).select_related("festival"):
        if sub.is_offense(now):
            what = "逾期窗歌" if sub.withdrawn_at else "逾期沒有繳交"
            return f"你在 {previous.name} 的〈{sub.title}〉{what}，依規定這次不能報曲。有疑問請找排歌組。"
    return None


# ── 撞曲、撞作品 ─────────────────────────────────────────────────────────────

def active_submissions(festival: Festival):
    return festival.submissions.filter(withdrawn_at__isnull=True, is_rejected=False)


# 社內與社內、社外與社外撞曲時直接擋下；社外跟社內撞曲，依社外投稿規則優先保留社內，
# 所以社內照樣可以報（社外那首會被標出來），社外則不能報社內已經報過的歌。
BLOCKING_SOURCES = {"member": ["member"], "partner": ["member", "partner"]}

GUEST_LIMIT = 5


def song_collision(festival: Festival, song_source: str, title: str, source: str, exclude_id=None):
    """同一場已經有人報了同一首歌（以歌曲出處 + 曲名判斷），只看會擋下 source 的那些來源"""
    qs = active_submissions(festival).filter(
        song_key=song_key(song_source, title), source__in=BLOCKING_SOURCES.get(source, [source])
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    # 同時撞到社內與社外時先回社內那首，訊息才會是「優先保留社內」
    return qs.filter(source="member").first() or qs.first()


def warnings_for(sub: Submission, others: list[Submission], previous_keys: set[str], now=None) -> list[dict]:
    """排歌組總覽上的提醒。others 是同一場其他還在出曲名單上的投稿。"""
    result = []

    def add(code, message):
        result.append({"code": code, "message": message})

    if not sub.is_active:
        return result
    for other in others:
        if other.pk == sub.pk:
            continue
        if other.song_key == sub.song_key:
            if sub.source == "partner" and other.source == "member":
                add("songCollision", f"跟社內 {other.editor_name} 撞曲，依社外投稿規則優先保留社內作品")
            else:
                add("songCollision", f"撞曲：{other.editor_name}〈{other.title}〉（{_source_label(other)}）")
        elif (
            other.source != sub.source
            and normalize(sub.visual_source) not in _GENERIC_VISUALS
            and normalize(other.visual_source) == normalize(sub.visual_source)
        ):
            add("workCollision", f"撞作品：{_source_label(other)}的 {other.editor_name}〈{other.title}〉也用《{sub.visual_source}》")

    if sub.source == "guest":
        same_person = [o for o in others if o.source == "guest" and _guest_id(o) == _guest_id(sub)]
        if len(same_person) > GUEST_LIMIT:
            add("guestLimit", f"{sub.editor_name} 投了 {len(same_person)} 首，亂入曲每人最多 {GUEST_LIMIT} 首")
        if sub.song_key in previous_keys:
            add("playedLastTime", "上一場播過，依亂入曲規則不入選")
        deadline = sub.festival.guest_deadline
        if deadline and sub.created_at > deadline:
            add("afterGuestDeadline", "超過亂入曲截止時間才投稿")
    if sub.chain_with_id:
        partner = next((o for o in others if o.pk == sub.chain_with_id), None)
        if partner is None:
            add("chainBroken", "連曲的另一首已經窗歌或退件")
        elif sub.duration_seconds and partner.duration_seconds and (
            sub.duration_seconds + partner.duration_seconds > Submission.CHAIN_MAX_SECONDS
        ):
            add("chainTooLong", f"連曲〈{sub.title}〉＋〈{partner.title}〉超過 10 分鐘")
    if sub.changed_after_upload:
        changed = timezone.localtime(sub.file_updated_at).strftime("%m/%d %H:%M")
        add("changedAfterUpload", f"繳交後改過檔案或長度（{changed}），播出前請確認是最新版")
    if sub.restricted_work:
        add("restrictedWork", "作品有公告禁止二創或限制")
    return result


def _source_label(sub: Submission) -> str:
    return sub.festival.partner_name if sub.source == "partner" else sub.get_source_display()


def _guest_id(sub: Submission) -> str:
    """亂入曲投稿人：有信箱用信箱，沒有用名字"""
    return (sub.contact_email or sub.editor_name).strip().lower()


def five_sec_counts(active: list[Submission], now=None) -> tuple[int, int]:
    """
    5 秒畫面的（要放的段數, 已繳的段數）。社內、社外每首各一段；
    亂入曲每位投稿人最多一段（每人最多 5 秒），不論投了幾首。
    """
    requested = uploaded = 0
    guests_requested, guests_uploaded = set(), set()
    for s in active:
        if s.source == "guest":
            if s.five_sec:
                guests_requested.add(_guest_id(s))
            if s.five_sec_status(now) == "uploaded":
                guests_uploaded.add(_guest_id(s))
        else:
            requested += s.five_sec
            uploaded += s.five_sec_status(now) == "uploaded"
    return requested + len(guests_requested), uploaded + len(guests_uploaded)


def previous_song_keys(festival: Festival) -> set[str]:
    previous = festival.previous_hall_festival()
    if previous is None:
        return set()
    return set(Play.objects.filter(festival=previous).values_list("song_key", flat=True))


# ── 投稿者能做什麼 ───────────────────────────────────────────────────────────

def permissions(sub: Submission, now=None) -> dict:
    now = now or timezone.now()
    active = sub.is_active
    report_open = sub.festival.is_report_open(sub.source, now)
    deadline = sub.upload_deadline
    before_upload_deadline = deadline is None or now <= deadline
    return {
        # 報曲截止前：可以改歌、直接刪除
        "canEditSong": active and report_open,
        "canDelete": active and report_open,
        # 報曲截止後：只能窗歌；繳交截止前可以填檔案與備註
        "canWithdraw": active and not report_open,
        "canEditDetails": active and before_upload_deadline,
        "withdrawIsLate": active and not report_open and sub.withdraw_is_late(now),
    }


def duration_field():
    return serializers.IntegerField(min_value=1, max_value=60 * 60, required=False, allow_null=True)


class SubmissionInput(serializers.Serializer):
    """社內、合作社團投稿與修改。欄位名稱跟前端一致（camelCase）。"""

    source = serializers.ChoiceField(choices=["member", "partner"], required=False)
    editorName = serializers.CharField(max_length=100, required=False, allow_blank=True)
    songSource = serializers.CharField(max_length=255)
    visualSource = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=255)
    artist = serializers.CharField(max_length=255, required=False, allow_blank=True)
    attributes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    songLink = serializers.CharField(max_length=500)
    remarks = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    restrictedWork = serializers.BooleanField(required=False)
    isBackup = serializers.BooleanField(required=False)
    fiveSec = serializers.BooleanField(required=False)
    chainWith = serializers.IntegerField(required=False, allow_null=True)
    fileLink = serializers.CharField(max_length=500, required=False, allow_blank=True)
    duration = duration_field()
    fiveSecLink = serializers.CharField(max_length=500, required=False, allow_blank=True)

    SONG_FIELDS = {
        "source": "source", "editorName": "editor_name", "songSource": "song_source",
        "visualSource": "visual_source", "title": "title", "artist": "artist",
        "restrictedWork": "restricted_work", "fiveSec": "five_sec", "isBackup": "is_backup",
    }
    DETAIL_FIELDS = {"attributes": "attributes", "songLink": "song_link", "remarks": "remarks"}

    def __init__(self, *args, festival: Festival, user, instance_obj: Submission | None = None, **kwargs):
        self.festival = festival
        self.user = user
        self.sub = instance_obj
        super().__init__(*args, **kwargs)

    def validate(self, data):
        now = timezone.now()
        sub = self.sub
        errors = {}

        if sub is None:
            source = data.get("source", "member")
            if not self.festival.is_report_open(source, now):
                raise serializers.ValidationError({"detail": "這一場的報曲已經截止（或還沒開放）"})
            reason = ban_reason(self.user, self.festival, now)
            if reason:
                raise serializers.ValidationError({"detail": reason})
            if source == "partner" and not data.get("isBackup"):
                count = active_submissions(self.festival).filter(source="partner", is_backup=False).count()
                if count >= self.festival.partner_limit:
                    raise serializers.ValidationError({
                        "source": f"{self.festival.partner_name}的新曲已經滿 {self.festival.partner_limit} 首，"
                                  "可以改報成備曲"
                    })
        else:
            perms = permissions(sub, now)
            if not sub.is_active:
                raise serializers.ValidationError({"detail": "這首已經窗歌或退件，不能再修改"})
            if not perms["canEditDetails"]:
                raise serializers.ValidationError({"detail": "已經過了繳交截止，要修改請找排歌組"})
            if not perms["canEditSong"]:
                for key, attr in self.SONG_FIELDS.items():
                    if key in data and data[key] != getattr(sub, attr):
                        errors[key] = "報曲截止後要換歌或改 5 秒畫面，請找排歌組"
            if errors:
                raise serializers.ValidationError(errors)

        song_source = data.get("songSource", sub.song_source if sub else "")
        title = data.get("title", sub.title if sub else "")
        song_changed = sub is None or song_key(song_source, title) != sub.song_key
        source = data.get("source", sub.source if sub else "member")
        other = song_collision(self.festival, song_source, title, source, exclude_id=sub.pk if sub else None)
        if song_changed and other is not None:
            if source == "partner" and other.source == "member":
                errors["title"] = "這首歌社內已經有人報了，依社外投稿規則優先保留社內作品，請換一首。"
            else:
                errors["title"] = (
                    f"這首歌 {other.editor_name} 已經報了，不接受兩人報同一首，請自行協調。"
                    "如果其實是不同首歌（例如同名的一般曲），請找排歌組。"
                )

        if data.get("chainWith"):
            error = self._chain_error(data["chainWith"])
            if error:
                errors["chainWith"] = error

        if data.get("isBackup") and data.get("source", sub.source if sub else "member") != "partner":
            errors["isBackup"] = "只有合作社團可以報備曲"

        file_link = data.get("fileLink", sub.file_link if sub else "")
        duration = data.get("duration", sub.duration_seconds if sub else None)
        if file_link and not duration:
            errors["duration"] = "繳交時請填影片長度"
        five_sec = data.get("fiveSec", sub.five_sec if sub else False)
        if data.get("fiveSecLink") and not five_sec:
            errors["fiveSecLink"] = "報曲時沒有選要上傳 5 秒畫面"

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def _chain_error(self, target_id: int) -> str | None:
        target = active_submissions(self.festival).filter(pk=target_id, submitter=self.user).first()
        if target is None or (self.sub and target.pk == self.sub.pk):
            return "連曲只能選自己這一場的另一首"
        mine = self.sub.pk if self.sub else None
        if target.chain_with_id not in (None, mine):
            return "那一首已經跟別首連曲了（每次至多 2 首）"
        # 已經有別首連到 target，或有別首連到自己
        others = active_submissions(self.festival).exclude(pk=target.pk)
        taken = Q(chain_with=target)
        if mine:
            others = others.exclude(pk=mine)
            taken |= Q(chain_with_id=mine)
        if others.filter(taken).exists():
            return "連曲每次至多 2 首"
        return None

    def save_submission(self) -> Submission:
        now = timezone.now()
        data = self.validated_data
        sub = self.sub or Submission(festival=self.festival, submitter=self.user, source=data.get("source", "member"))

        for key, attr in {**self.SONG_FIELDS, **self.DETAIL_FIELDS}.items():
            if key in data:
                setattr(sub, attr, data[key])
        if not sub.editor_name:
            sub.editor_name = self.user.name
        if "chainWith" in data:
            sub.chain_with_id = data["chainWith"] or None

        # 繳交：第一次填好連結與長度記為繳交時間；之後改檔案或長度另外記，讓排歌組知道要重新確認
        if "fileLink" in data or "duration" in data:
            link = data.get("fileLink", sub.file_link)
            duration = data.get("duration", sub.duration_seconds)
            changed = link != sub.file_link or duration != sub.duration_seconds
            sub.file_link, sub.duration_seconds = link, duration
            if not link:
                sub.uploaded_at = sub.file_updated_at = None
            elif sub.uploaded_at is None:
                sub.uploaded_at = now
            elif changed:
                sub.file_updated_at = now
                sub.file_checked = False
        if "fiveSecLink" in data:
            sub.five_sec_link = data["fiveSecLink"]
            if not sub.five_sec_link:
                sub.five_sec_uploaded_at = None
            elif sub.five_sec_uploaded_at is None:
                sub.five_sec_uploaded_at = now
        if not sub.five_sec:
            sub.five_sec_link, sub.five_sec_uploaded_at = "", None

        sub.save()
        return sub


class StaffUpdateInput(serializers.Serializer):
    """排歌組在總覽頁能直接改的欄位。換歌、補報等其他修改請到後台。"""

    fileChecked = serializers.BooleanField(required=False)
    extendedUntil = serializers.DateTimeField(required=False, allow_null=True)
    isRejected = serializers.BooleanField(required=False)
    rejectReason = serializers.CharField(max_length=200, required=False, allow_blank=True)
    penaltyWaived = serializers.BooleanField(required=False)
    duration = duration_field()
    libraryConsent = serializers.BooleanField(required=False)

    FIELDS = {
        "fileChecked": "file_checked", "extendedUntil": "extended_until", "isRejected": "is_rejected",
        "rejectReason": "reject_reason", "penaltyWaived": "penalty_waived", "duration": "duration_seconds",
        "libraryConsent": "library_consent",
    }

    def apply(self, sub: Submission) -> Submission:
        for key, attr in self.FIELDS.items():
            if key in self.validated_data:
                setattr(sub, attr, self.validated_data[key])
        if not sub.is_rejected:
            sub.reject_reason = ""
        sub.save()
        return sub
