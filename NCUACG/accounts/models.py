# NCUACG/accounts/models.py
from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError("必須提供 email")
        user = self.model(email=self.normalize_email(email), name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        # createsuperuser 建立的帳號不需要再做信箱驗證
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    全站唯一的帳號（settings.AUTH_USER_MODEL）。網站登入與 Django admin 共用同一組帳號。

    角色：
      - 社員：一般帳號
      - 幹部：is_staff=True，可以登入 /admin 管理社課、作品、留言與活動（見 OFFICER_APP_LABELS）
      - 超管：is_superuser=True，擁有全部權限（包括指定誰是幹部）
    """

    # 幹部在 Django admin 可以完整管理的 app；其他 app（帳號等）只有超管能動
    OFFICER_APP_LABELS = {"club", "event"}

    email = models.EmailField("email", unique=True)
    name = models.CharField("名稱", max_length=100)
    registered_at = models.DateTimeField("註冊時間", auto_now_add=True)
    # 註冊後要點驗證信才會變成 True；未驗證的帳號不能登入
    is_active = models.BooleanField("已驗證信箱", default=False)
    is_staff = models.BooleanField(
        "幹部",
        default=False,
        help_text="勾選後可以登入後台，管理社課、成果牆與活動。",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = "帳號"
        verbose_name_plural = "帳號"

    def __str__(self):
        return f"{self.name} ({self.email})"

    # 幹部只要勾一個「幹部」就能管理社團內容，不必再逐一設定權限或群組
    def has_perm(self, perm, obj=None):
        if self.is_active and self.is_staff and perm.split(".", 1)[0] in self.OFFICER_APP_LABELS:
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if self.is_active and self.is_staff and app_label in self.OFFICER_APP_LABELS:
            return True
        return super().has_module_perms(app_label)


class VerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)
