from django.db import models
from django.utils import timezone
from datetime import timedelta

class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)

    # DRF 的 IsAuthenticated 會讀 is_authenticated / is_anonymous。
    # 這裡刻意用 property 而不是資料庫欄位：本專案走無狀態 JWT，
    # 「有沒有登入」由 token 是否驗得過決定。先前存成 BooleanField 的做法，
    # 登入時設 True、登出時卻沒有設回 False，等於變成「這個人有沒有登入過」。
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self):
        return f"{self.name} ({self.email})"


class Credential(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='credential')
    password_hash = models.CharField(max_length=256)

    def __str__(self):
        return f"(user_id={self.user.id})"


class VerificationToken(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)



