# NCUACG/accounts/tests.py
from datetime import timedelta

from captcha.models import CaptchaStore
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, VerificationToken

PASSWORD = "Test-password-123"


def make_user(email="member@example.test", *, active=True, **extra):
    return User.objects.create_user(
        email=email, name=email.split("@")[0], password=PASSWORD, is_active=active, **extra
    )


def auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def login(self, answer="abcde", **overrides):
        captcha = CaptchaStore.objects.create(challenge="ABCDE", response="abcde")
        payload = {
            "useremail": self.user.email,
            "password": PASSWORD,
            "captcha_key": captcha.hashkey,
            "captcha_value": answer,
            **overrides,
        }
        return self.client.post("/api/login/", payload, format="json"), captcha

    def test_login_success_returns_tokens(self):
        res, _ = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_captcha_is_case_insensitive(self):
        res, _ = self.login(answer="ABCDE")
        self.assertEqual(res.status_code, 200)

    def test_captcha_is_single_use_even_when_wrong(self):
        res, captcha = self.login(answer="wrong")
        self.assertEqual(res.status_code, 400)
        self.assertIn("captcha", res.data)
        self.assertFalse(CaptchaStore.objects.filter(pk=captcha.pk).exists())

    def test_wrong_password(self):
        res, _ = self.login(password="nope")
        self.assertEqual(res.status_code, 400)
        self.assertIn("useremail", res.data)

    def test_unverified_user_gets_unverified_flag(self):
        self.user.is_active = False
        self.user.save()
        res, _ = self.login()
        self.assertEqual(res.status_code, 400)
        self.assertIn("unverified", res.data)


class TokenTests(TestCase):
    def test_me_with_access_token(self):
        user = make_user(is_staff=True)
        res = auth_client(user).get("/api/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["id"], user.id)
        self.assertEqual(res.data["role"], "admin")

    def test_me_without_token(self):
        self.assertEqual(APIClient().get("/api/me/").status_code, 401)

    def test_refresh_rotates_tokens(self):
        user = make_user()
        res = APIClient().post("/api/token/refresh/", {"refresh": str(RefreshToken.for_user(user))}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_me_reports_superadmin(self):
        user = User.objects.create_superuser(email="root@example.test", name="root", password=PASSWORD)
        self.assertEqual(auth_client(user).get("/api/me/").data["role"], "superadmin")

    def test_refresh_rejected_for_deleted_user(self):
        user = make_user()
        refresh = str(RefreshToken.for_user(user))
        user.delete()
        res = APIClient().post("/api/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_refresh_rejected_for_inactive_user(self):
        user = make_user(active=False)
        res = APIClient().post("/api/token/refresh/", {"refresh": str(RefreshToken.for_user(user))}, format="json")
        self.assertEqual(res.status_code, 401)


class VerificationTests(TestCase):
    def setUp(self):
        cache.clear()  # 重寄驗證信的節流記在 cache
        self.client = APIClient()
        self.user = make_user(active=False)

    def test_register_sends_frontend_link(self):
        res = self.client.post(
            "/api/register/",
            {"name": "newbie", "useremail": "newbie@example.test", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify-email?token=", mail.outbox[0].body)

    def test_verify_with_post(self):
        token = VerificationToken.objects.create(user=self.user, token="t1")
        res = self.client.post("/api/verify-registration/", {"token": token.token}, format="json")
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_verify_link_is_single_use(self):
        VerificationToken.objects.create(user=self.user, token="t1")
        self.client.post("/api/verify-registration/", {"token": "t1"}, format="json")
        res = self.client.post("/api/verify-registration/", {"token": "t1"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_verify_with_get_still_works_for_old_emails(self):
        VerificationToken.objects.create(user=self.user, token="t1")
        res = self.client.get("/api/verify-registration/?token=t1")
        self.assertEqual(res.status_code, 200)

    def test_expired_link(self):
        token = VerificationToken.objects.create(user=self.user, token="t1")
        VerificationToken.objects.filter(pk=token.pk).update(created_at=timezone.now() - timedelta(hours=25))
        res = self.client.post("/api/verify-registration/", {"token": "t1"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_resend_invalidates_old_link(self):
        VerificationToken.objects.create(user=self.user, token="old")
        VerificationToken.objects.filter(token="old").update(created_at=timezone.now() - timedelta(minutes=5))
        res = self.client.post("/api/resend-verification/", {"useremail": self.user.email}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(VerificationToken.objects.get(token="old").is_used)
        self.assertEqual(VerificationToken.objects.filter(user=self.user, is_used=False).count(), 1)

    def test_resend_has_cooldown(self):
        VerificationToken.objects.create(user=self.user, token="fresh")
        res = self.client.post("/api/resend-verification/", {"useremail": self.user.email}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_does_not_reveal_unknown_email(self):
        known = self.client.post("/api/resend-verification/", {"useremail": self.user.email}, format="json")
        unknown = self.client.post("/api/resend-verification/", {"useremail": "nobody@example.test"}, format="json")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_resend_is_throttled(self):
        for _ in range(5):
            self.client.post("/api/resend-verification/", {"useremail": "x@example.test"}, format="json")
        res = self.client.post("/api/resend-verification/", {"useremail": "x@example.test"}, format="json")
        self.assertEqual(res.status_code, 429)


class AdminSiteTests(TestCase):
    """網站帳號就是後台帳號：幹部用同一組 email / 密碼登入 /admin。"""

    def test_officer_can_manage_club_and_event_but_not_accounts(self):
        officer = make_user("officer@example.test", is_staff=True)
        self.client.force_login(officer)
        self.assertEqual(self.client.get("/admin/club/work/").status_code, 200)
        self.assertEqual(self.client.get("/admin/event/event/add/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 403)

    def test_member_cannot_enter_admin(self):
        self.client.force_login(make_user())
        res = self.client.get("/admin/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin/login/", res["Location"])

    def test_admin_login_with_site_credentials(self):
        make_user("officer@example.test", is_staff=True)
        res = self.client.post(
            "/admin/login/?next=/admin/",
            {"username": "officer@example.test", "password": PASSWORD},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], "/admin/")

    def test_superuser_can_promote_officer(self):
        root = User.objects.create_superuser(email="root@example.test", name="root", password=PASSWORD)
        self.client.force_login(root)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
