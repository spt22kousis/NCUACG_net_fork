# NCUACG/songfest/submission_views.py
"""
新曲投稿 API（掛在 /api/songfest/ 之下）。規則都在 submissions.py。

投稿者（需登入）
  GET    active/                                   目前在準備的那一場、截止時間、我能不能報曲
  GET    festivals/<id>/submissions/               回報串：這場的社內與合作社團投稿（不含亂入）
  POST   festivals/<id>/submissions/               報曲
  GET    festivals/<id>/my-submissions/            我的投稿（含繳交資料與可以做的操作）
  PATCH  submissions/<id>/                         修改、繳交
  DELETE submissions/<id>/                         報曲截止前刪除
  POST   submissions/<id>/withdraw/                報曲截止後窗歌
  GET    submissions/<id>/comments/                閒聊
  POST   submissions/<id>/comments/
  DELETE submission-comments/<id>/                 刪除留言（本人或排歌組）

排歌組（幹部或該場排歌組成員）
  GET    manage/festivals/                         我能管理的場次
  GET    festivals/<id>/manage/                    總覽：所有投稿、提醒、統計
  PATCH  manage/submissions/<id>/                  確認檔案、延期、退件、免除罰則、填長度
  GET    festivals/<id>/manage/export/             匯出 CSV
  POST   festivals/<id>/manage/import-guests/      匯入亂入曲 Google 表單回覆（.xlsx）
"""
from __future__ import annotations

import csv
from io import StringIO
from urllib.parse import quote

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .importers import SpreadsheetError, import_guest_form
from .models import Festival, FestivalStaff, Submission, SubmissionComment
from .submissions import (
    StaffUpdateInput, SubmissionInput, ban_reason, is_officer, is_staff_for, permissions,
    previous_song_keys, warnings_for,
)
from .views import _festival_to_dict


def _iso(value):
    return timezone.localtime(value).isoformat() if value else None


def _user(request):
    return request.user if getattr(request.user, "is_authenticated", False) else None


def _forbidden(message="只有這一場的排歌組或幹部可以使用"):
    return Response({"detail": message}, status=status.HTTP_403_FORBIDDEN)


# ── 輸出格式 ────────────────────────────────────────────────────────────────

def festival_info(f: Festival) -> dict:
    now = timezone.now()
    return {
        **_festival_to_dict(f),
        "reportDeadline": _iso(f.report_deadline),
        "partnerDeadline": _iso(f.report_deadline_for("partner")),
        "withdrawDeadline": _iso(f.withdraw_deadline),
        "uploadDeadline": _iso(f.upload_deadline),
        "guestDeadline": _iso(f.guest_deadline),
        "reportOpen": {"member": f.is_report_open("member", now), "partner": f.is_report_open("partner", now)},
        "partnerName": f.partner_name,
        "partnerLimit": f.partner_limit,
        "rules": f.rules,
        "guestFormUrl": f.guest_form_url,
        "guestInfo": f.guest_info,
    }


def _source_label(sub: Submission) -> str:
    return sub.festival.partner_name if sub.source == "partner" else sub.get_source_display()


def submission_public(sub: Submission, user, now) -> dict:
    return {
        "id": sub.id,
        "source": sub.source,
        "sourceLabel": _source_label(sub),
        "editorName": sub.editor_name,
        "songSource": sub.song_source,
        "visualSource": sub.visual_source,
        "title": sub.title,
        "artist": sub.artist,
        "attributes": sub.attributes,
        "songLink": sub.song_link,
        "remarks": sub.remarks,
        "restrictedWork": sub.restricted_work,
        "fiveSec": sub.five_sec,
        "status": sub.status(now),
        "isMine": user is not None and sub.submitter_id == user.pk,
        "commentCount": getattr(sub, "comment_count", 0),
        "createdAt": _iso(sub.created_at),
    }


def submission_mine(sub: Submission, user, now) -> dict:
    return {
        **submission_public(sub, user, now),
        "fileLink": sub.file_link,
        "duration": sub.duration_seconds,
        "uploadedAt": _iso(sub.uploaded_at),
        "fileUpdatedAt": _iso(sub.file_updated_at),
        "fiveSecLink": sub.five_sec_link,
        "fiveSecStatus": sub.five_sec_status(now),
        "uploadDeadline": _iso(sub.upload_deadline),
        "extendedUntil": _iso(sub.extended_until),
        "chainWith": sub.chain_with_id,
        "withdrawnAt": _iso(sub.withdrawn_at),
        "rejectReason": sub.reject_reason if sub.is_rejected else "",
        "permissions": permissions(sub, now),
    }


def submission_staff(sub: Submission, user, now, warnings) -> dict:
    return {
        **submission_mine(sub, user, now),
        "submitterName": sub.submitter.name if sub.submitter else None,
        "contactEmail": sub.contact_email,
        "guestMessage": sub.guest_message,
        "libraryConsent": sub.library_consent,
        "fileChecked": sub.file_checked,
        "penaltyWaived": sub.penalty_waived,
        "isOffense": sub.is_offense(now),
        "changedAfterUpload": sub.changed_after_upload,
        "warnings": warnings,
    }


def _with_comment_count(qs):
    return qs.select_related("festival", "submitter").annotate(comment_count=Count("comments"))


# ── 投稿者 ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def active_festival(request):
    festival = Festival.active()
    if festival is None:
        return Response({"festival": None, "viewer": None})
    user = _user(request)
    viewer = None
    if user is not None:
        viewer = {"banReason": ban_reason(user, festival), "isStaff": is_staff_for(user, festival)}
    return Response({"festival": festival_info(festival), "viewer": viewer})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def festival_submissions(request, festival_id: int):
    festival = get_object_or_404(Festival, pk=festival_id, is_published=True)
    now = timezone.now()
    if request.method == "GET":
        # 回報串：亂入曲由排歌組處理，不列在這裡；退件的只有本人看得到
        subs = _with_comment_count(
            festival.submissions.exclude(source="guest").exclude(Q(is_rejected=True) & ~Q(submitter=request.user))
        )
        return Response([submission_public(s, request.user, now) for s in subs])

    form = SubmissionInput(data=request.data, festival=festival, user=request.user)
    form.is_valid(raise_exception=True)
    sub = form.save_submission()
    return Response(submission_mine(sub, request.user, now), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_submissions(request, festival_id: int):
    festival = get_object_or_404(Festival, pk=festival_id, is_published=True)
    now = timezone.now()
    subs = _with_comment_count(festival.submissions.filter(submitter=request.user))
    return Response([submission_mine(s, request.user, now) for s in subs])


def _own_submission(request, submission_id):
    return get_object_or_404(Submission.objects.select_related("festival"), pk=submission_id, submitter=request.user)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def submission_detail(request, submission_id: int):
    sub = _own_submission(request, submission_id)
    now = timezone.now()
    if request.method == "DELETE":
        if not permissions(sub, now)["canDelete"]:
            return Response({"detail": "報曲截止後不能刪除，請改用窗歌"}, status=status.HTTP_400_BAD_REQUEST)
        sub.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    form = SubmissionInput(data=request.data, partial=True, festival=sub.festival, user=request.user, instance_obj=sub)
    form.is_valid(raise_exception=True)
    sub = form.save_submission()
    return Response(submission_mine(sub, request.user, now))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submission_withdraw(request, submission_id: int):
    sub = _own_submission(request, submission_id)
    now = timezone.now()
    if not permissions(sub, now)["canWithdraw"]:
        return Response({"detail": "報曲截止前請直接刪除"}, status=status.HTTP_400_BAD_REQUEST)
    sub.withdrawn_at = now
    sub.save(update_fields=["withdrawn_at", "updated_at"])
    return Response(submission_mine(sub, request.user, now))


def _comment_to_dict(c: SubmissionComment, user, staff: bool) -> dict:
    return {
        "id": c.id,
        "username": c.user.name,
        "content": c.content,
        "createdAt": _iso(c.created_at),
        "canDelete": staff or c.user_id == user.pk,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def submission_comments(request, submission_id: int):
    sub = get_object_or_404(
        Submission.objects.select_related("festival").exclude(source="guest"), pk=submission_id
    )
    staff = is_staff_for(request.user, sub.festival)
    if request.method == "GET":
        comments = sub.comments.select_related("user")
        return Response([_comment_to_dict(c, request.user, staff) for c in comments])

    content = str(request.data.get("content", "")).strip()
    if not content:
        return Response({"content": ["請輸入內容"]}, status=status.HTTP_400_BAD_REQUEST)
    if len(content) > 500:
        return Response({"content": ["最多 500 字"]}, status=status.HTTP_400_BAD_REQUEST)
    comment = SubmissionComment.objects.create(submission=sub, user=request.user, content=content)
    return Response(_comment_to_dict(comment, request.user, staff), status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def submission_comment_delete(request, comment_id: int):
    comment = get_object_or_404(SubmissionComment.objects.select_related("submission__festival"), pk=comment_id)
    if comment.user_id != request.user.pk and not is_staff_for(request.user, comment.submission.festival):
        return Response({"detail": "只能刪除自己的留言"}, status=status.HTTP_403_FORBIDDEN)
    comment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── 排歌組 ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def manage_festivals(request):
    """幹部看得到之後的場次與有投稿的場次；排歌組成員只看得到自己負責的場次。"""
    festivals = Festival.objects.filter(kind="hall")
    if is_officer(request.user):
        festivals = festivals.filter(
            Q(date__gte=timezone.localdate()) | Q(submissions__isnull=False)
        ).distinct()
    else:
        festivals = festivals.filter(
            pk__in=FestivalStaff.objects.filter(user=request.user).values("festival")
        )
    return Response([{"id": f.id, "name": f.name, "date": f.date.isoformat()} for f in festivals])


def _summary(subs: list[Submission], festival: Festival, now) -> dict:
    active = [s for s in subs if s.is_active]
    durations = [s.duration_seconds for s in active if s.duration_seconds]
    return {
        "active": len(active),
        "bySource": {key: sum(1 for s in active if s.source == key) for key, _ in Submission.SOURCE_CHOICES},
        "partnerLimit": festival.partner_limit,
        "uploaded": sum(1 for s in active if s.status(now) == "uploaded"),
        "overdue": sum(1 for s in active if s.status(now) == "overdue"),
        "withdrawn": sum(1 for s in subs if s.withdrawn_at),
        "rejected": sum(1 for s in subs if s.is_rejected),
        "fiveSecRequested": sum(1 for s in active if s.five_sec),
        "fiveSecUploaded": sum(1 for s in active if s.five_sec_status(now) == "uploaded"),
        "totalDuration": sum(durations),
        "missingDuration": len(active) - len(durations),
    }


def _staff_rows(festival: Festival, user, now):
    subs = list(_with_comment_count(festival.submissions.all()))
    active = [s for s in subs if s.is_active]
    previous = previous_song_keys(festival)
    rows = [submission_staff(s, user, now, warnings_for(s, active, previous, now)) for s in subs]
    return subs, rows


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def manage_overview(request, festival_id: int):
    festival = get_object_or_404(Festival, pk=festival_id)
    if not is_staff_for(request.user, festival):
        return _forbidden()
    now = timezone.now()
    subs, rows = _staff_rows(festival, request.user, now)
    return Response({
        "festival": festival_info(festival),
        "summary": _summary(subs, festival, now),
        "submissions": rows,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def manage_submission(request, submission_id: int):
    sub = get_object_or_404(Submission.objects.select_related("festival", "submitter"), pk=submission_id)
    if not is_staff_for(request.user, sub.festival):
        return _forbidden()
    form = StaffUpdateInput(data=request.data, partial=True)
    form.is_valid(raise_exception=True)
    form.apply(sub)
    now = timezone.now()
    active = list(sub.festival.submissions.filter(withdrawn_at__isnull=True, is_rejected=False))
    warnings = warnings_for(sub, active, previous_song_keys(sub.festival), now)
    return Response(submission_staff(sub, request.user, now, warnings))


CSV_COLUMNS = [
    "來源", "狀態", "歌曲出處", "畫面出處", "曲名", "原唱歌手", "製作者", "長度", "是否上傳五秒", "5秒狀態",
    "畫面或作品屬性", "歌曲連結", "備註", "檔案連結", "5秒連結", "繳交時間", "聯絡信箱", "提醒",
]
FIVE_SEC_LABELS = {"none": "否", "pending": "待繳", "uploaded": "已繳", "cancelled": "取消"}


def _mmss(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def manage_export(request, festival_id: int):
    """欄位順序照原本的「新曲」工作表，方便貼回排歌組的試算表。"""
    festival = get_object_or_404(Festival, pk=festival_id)
    if not is_staff_for(request.user, festival):
        return _forbidden()
    now = timezone.now()
    subs, rows = _staff_rows(festival, request.user, now)

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for sub, r in zip(subs, rows):
        writer.writerow([
            r["sourceLabel"], Submission.STATUS_LABELS[r["status"]], r["songSource"], r["visualSource"], r["title"],
            r["artist"], r["editorName"], _mmss(r["duration"]), "是" if r["fiveSec"] else "否",
            FIVE_SEC_LABELS[r["fiveSecStatus"]], r["attributes"], r["songLink"], r["remarks"], r["fileLink"],
            r["fiveSecLink"],
            timezone.localtime(sub.uploaded_at).strftime("%Y/%m/%d %H:%M") if sub.uploaded_at else "",
            r["contactEmail"], "；".join(w["message"] for w in r["warnings"]),
        ])
    # 加 BOM，Excel 打開中文才不會變亂碼
    response = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    filename = quote(f"{festival.name}_新曲.csv")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def manage_import_guests(request, festival_id: int):
    festival = get_object_or_404(Festival, pk=festival_id)
    if not is_staff_for(request.user, festival):
        return _forbidden()
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"file": ["請選擇 Google 表單回覆下載的 .xlsx"]}, status=status.HTTP_400_BAD_REQUEST)
    try:
        report = import_guest_form(festival, upload)
    except SpreadsheetError as exc:
        return Response({"file": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"lines": report.lines, "warnings": report.warnings})
