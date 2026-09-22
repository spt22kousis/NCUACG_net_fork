from rest_framework import serializers

from django.contrib.auth.password_validation import validate_password
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics
import bcrypt
from accounts.models import User, Credential, VerificationToken
from django.db import transaction
from django.utils import timezone
from captcha.models import CaptchaStore
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from .verifyemail import generate_verification_token, send_verification_email
import os
import logging

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
        user = User.objects.filter(email=useremail).first()
        if not user:
            raise serializers.ValidationError({"useremail": "帳號或密碼錯誤"})

        cred = getattr(user, 'credential', None)
        if not cred or not bcrypt.checkpw(password.encode('utf-8'), cred.password_hash.encode('utf-8')):
            raise serializers.ValidationError({"useremail": "帳號或密碼錯誤"})

        if not user.is_active:
            raise serializers.ValidationError({"useremail": "你尚未驗證email"})

        # 更新 last_login
        with transaction.atomic():
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

        # 簽發 JWT
        refresh = RefreshToken.for_user(user) 
        refresh['id'] = int(user.pk)
        refresh["user_id"] = int(user.pk)  # 加這行
        attrs['user'] = user
        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)
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
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("此 Email 已註冊過")
        return value

    def create(self, validated_data):
        name = validated_data['name']
        email = validated_data['useremail']
        password = validated_data['password']

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        with transaction.atomic():
            # 建立未啟用帳號
            user = User.objects.create(
                name=name,
                email=email,
                is_active=False
            )
            # 建立 Credential
            Credential.objects.create(
                user=user,
                password_hash=hashed.decode('utf-8')
            )
            # 建立驗證 token
            token = generate_verification_token()
            VerificationToken.objects.create(user=user, token=token)
            # 發送驗證信
            send_verification_email(email, token)

        return user


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    用 refresh token 換新的 access token。

    為什麼要自己寫：SimpleJWT 內建的版本會執行
        get_user_model().objects.get(**{USER_ID_FIELD: user_id})
    去撈使用者，而 get_user_model() 指向 django.contrib.auth 的 User。
    本專案的使用者是自訂的 accounts.User（沒有設成 AUTH_USER_MODEL），
    那張表永遠查不到，結果是每次續命都 DoesNotExist → 500。
    這裡把那段查詢換成查 accounts.User，其餘輪替邏輯與上游一致。

    註：輪替區塊是照著 simplejwt 5.5.1 的實作寫的，升級套件時要回來對一下。
    """

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM, None)
        if user_id is not None:
            user = User.objects.filter(pk=user_id).first()
            # 帳號被刪掉或被停用時，手上的 refresh token 就該失效
            if user is None or not user.is_active:
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"], "no_active_account"
                )

        data = {"access": str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    # 沒裝 blacklist app 時沒有這個方法，忽略即可
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh.outstand()

            data["refresh"] = str(refresh)

        return data
