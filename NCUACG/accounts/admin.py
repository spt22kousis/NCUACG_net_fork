# NCUACG/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm as BaseUserChangeForm

from .models import User, VerificationToken


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name")


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    只有超管看得到這頁（幹部的權限只涵蓋社課與活動，見 User.has_perm）。
    要讓某人成為幹部：打開他的帳號，勾選「幹部」即可。
    """

    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ("email", "name", "is_active", "is_staff", "is_superuser", "registered_at", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "name")
    ordering = ("-registered_at",)
    readonly_fields = ("registered_at", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "name", "password")}),
        ("身分", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("進階權限（一般不需要設定）", {"classes": ("collapse",), "fields": ("groups", "user_permissions")}),
        ("時間", {"fields": ("registered_at", "last_login")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "password1", "password2", "is_active", "is_staff"),
        }),
    )


@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "is_used")
    list_filter = ("is_used",)
    search_fields = ("user__email",)
    # 驗證連結等同一次性密碼，不在後台顯示 token 本身
    fields = ("user", "created_at", "is_used")
    readonly_fields = ("user", "created_at")

