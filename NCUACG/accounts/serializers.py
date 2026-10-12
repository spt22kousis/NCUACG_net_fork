# NCUACG/accounts/serializers.py
from captcha.models import CaptchaStore
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, VerificationToken
from .verifyemail import generate_verification_token, send_verification_email


class LoginSerializer(serializers.Serializer):
    useremail = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    captcha_key = serializers.CharField()
    captcha_value = serializers.CharField()

    def validate(self, attrs):
        useremail = attrs.get("useremail")
        password = attrs.get("password")
        captcha_key = attrs.get("captcha_key")
        captcha_value = attrs.get("captcha_value")

        # 驗證 Captcha：一組驗證碼只能用一次（不論答對答錯），並且要檢查是否過期。
        # 原本比對完沒有刪除，同一組 key + 答案可以無限重送，等於沒有擋暴力破解。
        captcha_obj = CaptchaStore.objects.filter(hashkey=captcha_key).first()
        if captcha_obj is None:
            raise serializers.ValidationError({"captcha": "驗證碼已失效，請重新取得"})

        expected = captcha_obj.response
        expired = captcha_obj.expiration <= timezone.now()
        # 用 delete() 的回傳筆數判斷「是不是我刪掉的」：同一組 key 同時送兩次時，
        # 只有一個請求能刪到，另一個會拿到 0，視同已失效（避免競態重複使用）
        deleted, _ = CaptchaStore.objects.filter(pk=captcha_obj.pk).delete()
        if deleted == 0 or expired:
            raise serializers.ValidationError({"captcha": "驗證碼已失效，請重新取得"})

        # 套件存檔時會把答案轉小寫，所以比對不分大小寫
        if expected != captcha_value.strip().lower():
            raise serializers.ValidationError({"captcha": "驗證碼錯誤"})

        # 驗證帳密
        user = User.objects.filter(email__iexact=useremail).first()
        if user is None:
            # 帳號不存在時也跑一次雜湊，讓回應時間跟「密碼錯誤」差不多，避免被用來探測哪些信箱註冊過
            User().set_password(password)
            raise serializers.ValidationError({"useremail": "帳號或密碼錯誤"})

        if not user.check_password(password):
            raise serializers.ValidationError({"useremail": "帳號或密碼錯誤"})

        if not user.is_active:
            # unverified 讓前端知道要顯示「重寄驗證信」按鈕
            raise serializers.ValidationError({
                "useremail": "你尚未驗證 email，請先點擊驗證信中的連結",
                "unverified": "true",
            })

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # 簽發 JWT（for_user 會依 SIMPLE_JWT 的 USER_ID_CLAIM 放入使用者 id）
        refresh = RefreshToken.for_user(user)
        attrs["user"] = user
        attrs["access"] = str(refresh.access_token)
        attrs["refresh"] = str(refresh)
        return attrs


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    useremail = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    def validate_name(self, value):
        if User.objects.filter(name=value).exists():
            raise serializers.ValidationError("此名字已被使用")
        return value

    def validate_useremail(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("此 Email 已註冊過")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            # 建立未啟用帳號，點了驗證信才會啟用
            user = User.objects.create_user(
                email=validated_data["useremail"],
                name=validated_data["name"],
                password=validated_data["password"],
                is_active=False,
            )
            token = generate_verification_token()
            VerificationToken.objects.create(user=user, token=token)
            send_verification_email(user.email, token)

        return user


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    SimpleJWT 內建的續命會用 objects.get() 查使用者，帳號被刪掉時會丟 DoesNotExist 變成 500；
    這裡改成回 401，前端攔截器就會把使用者登出。帳號停用的情況內建版本已經會擋。
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            )
