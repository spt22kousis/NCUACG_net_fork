# NCUACG/accounts/views.py
import logging
import traceback
from datetime import timedelta

from captcha.helpers import captcha_image_url
from captcha.models import CaptchaStore
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import User, VerificationToken
from accounts.serializers import CustomTokenRefreshSerializer, LoginSerializer, RegisterSerializer
from .verifyemail import generate_verification_token, send_verification_email

logger = logging.getLogger(__name__)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            role = "member"
            if user.is_superuser:
                role = "superadmin"
            elif user.is_staff:
                role = "admin"

            # 排歌組成員不一定是幹部，側邊欄的「管理歌單」要另外判斷
            from songfest.submissions import is_songfest_staff

            response_data = {
                "id": user.id,
                "username": user.name,
                "role": role,
                "songfestStaff": is_songfest_staff(user),
            }

            # 注意：不要在這裡用 print() 輸出 emoji/中文，Windows 終端機 (cp950)
            # 會丟 UnicodeEncodeError，被下面的 except 吞掉後整支 API 變成 500。
            logger.info("Profile returned for user id=%s", user.id)
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception:
            logger.error(traceback.format_exc())
            return Response({"error": "取得個人資料時發生錯誤"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCaptcha(APIView):
    # 公開端點：不驗身分，避免帶著舊 token 的人拿不到驗證碼
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        new_captcha = CaptchaStore.generate_key()
        image_url = captcha_image_url(new_captcha)
        return Response({
            "captcha_key": new_captcha,
            "captcha_image_url": image_url
        })


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # 驗證失敗（驗證碼、帳密、未驗證信箱）直接讓 DRF 回標準格式：
        #   400 {"captcha": ["驗證碼錯誤"]} / {"useremail": ["帳號或密碼錯誤"]}
        # 原本整段包在 except Exception 裡用 str(e) 回傳，前端只能用正規表示式
        # 從 "ErrorDetail(string='...')" 裡撈字，而且真正的程式錯誤也會被偽裝成 400。
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        logger.info("User id=%s logged in successfully.", user.id)

        return Response({
            "message": "登入成功",
            "access": serializer.validated_data["access"],
            "refresh": serializer.validated_data["refresh"],
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({'message': '登出成功'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # 呼叫 create()
        return Response({'message': '註冊成功，請查收驗證信'}, status=status.HTTP_201_CREATED)
        

class VerifyRegistrationView(APIView):
    """
    完成 email 驗證。前端驗證頁（/verify-email）用 POST {"token": ...} 呼叫；
    GET ?token=... 保留給先前寄出、直接連到 API 的舊驗證信。
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return self._verify(request.query_params.get("token"))

    def post(self, request):
        return self._verify(request.data.get("token"))

    def _verify(self, token_value):
        token_obj = VerificationToken.objects.filter(token=token_value, is_used=False).first() if token_value else None

        if not token_obj or token_obj.is_expired():
            return Response({"error": "驗證連結無效或已過期"}, status=status.HTTP_400_BAD_REQUEST)

        # 驗證成功
        with transaction.atomic():
            token_obj.is_used = True
            token_obj.save(update_fields=["is_used"])
            token_obj.user.is_active = True
            token_obj.user.save(update_fields=["is_active"])

        return Response({"message": "驗證成功，註冊完成"}, status=status.HTTP_200_OK)


class ResendVerificationThrottle(AnonRateThrottle):
    """同一個 IP 一小時最多重寄 5 次，避免被拿來對別人的信箱轟炸"""
    scope = "resend_verification"
    rate = "5/hour"


class ResendVerificationView(APIView):
    """
    重寄驗證信。驗證連結 24 小時就過期，過期後沒有這支 API 帳號就卡死了。

    不論信箱存不存在、是否已驗證，都回同一句話，避免被用來探測哪些信箱註冊過。
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResendVerificationThrottle]

    # 同一個帳號兩次重寄至少間隔多久
    COOLDOWN = timedelta(minutes=1)

    def post(self, request):
        email = str(request.data.get("useremail", "")).strip()
        generic = Response(
            {"message": "如果這個信箱已註冊且尚未驗證，我們已重新寄出驗證信，請查看收件匣"},
            status=status.HTTP_200_OK,
        )
        if not email:
            return Response({"useremail": ["請輸入 email"]}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email, is_active=False).first()
        if user is None:
            return generic

        latest = VerificationToken.objects.filter(user=user).order_by("-created_at").first()
        if latest and latest.created_at > timezone.now() - self.COOLDOWN:
            return generic

        with transaction.atomic():
            # 舊連結一律作廢，只有最新一封信的連結有效
            VerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
            token = generate_verification_token()
            VerificationToken.objects.create(user=user, token=token)
        send_verification_email(user.email, token)
        return generic


class CustomTokenRefreshView(TokenRefreshView):
    """/api/token/refresh/ ：帳號被刪掉時回 401 而不是 500（見 CustomTokenRefreshSerializer）。"""
    serializer_class = CustomTokenRefreshSerializer
