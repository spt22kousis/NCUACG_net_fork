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
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from .verifyemail import generate_verification_token, send_verification_email
import os
import logging
from accounts.serializers import RegisterSerializer, LoginSerializer, CustomTokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView
import traceback
logger = logging.getLogger(__name__)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user  # 全站預設的 CustomJWTAuthentication 回傳的 accounts.User

            role = "member"
            if getattr(user, "is_super_admin", False):
                role = "superadmin"
            elif getattr(user, "is_admin", False):
                role = "admin"

            response_data = {
                "id": user.id,
                "username": getattr(user, "name", ""),  # 你的 User 是用 name
                "role": role,
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
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        token_value = request.query_params.get("token")
        token_obj = VerificationToken.objects.filter(token=token_value, is_used=False).first()

        if not token_obj or token_obj.is_expired():
            return Response({"error": "驗證連結無效或已過期"}, status=status.HTTP_400_BAD_REQUEST)

        # 驗證成功
        token_obj.is_used = True
        token_obj.save()
        token_obj.user.is_active = True
        token_obj.user.save()

        return Response({"message": "驗證成功，註冊完成"}, status=status.HTTP_200_OK)
    
class Super_adminView(APIView):
    def post(self, request):
        super_admin_password = request.data.get("super_admin_password")
        useremail = request.data.get("useremail")
        password = request.data.get("password")
        # 超級網管註冊
        if super_admin_password == os.getenv("super_admin_password"):
            if not User.objects.filter(is_super_admin=True).exists():
                user = User.objects.filter(email=useremail).first()
                cred = Credential.objects.filter(user=user).first()
                if user:
                    if bcrypt.checkpw(password.encode('utf-8'), cred.password_hash.encode('utf-8')):
                        user.is_super_admin = True
                        user.is_admin = True
                        user.save()
                        return Response({"message": "已成功成為網管"}, status=201)
                    else:
                        return Response({"error": "用戶密碼錯誤"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": "此用戶不存在"}, status=status.HTTP_400_BAD_REQUEST)
                
            else:
                return Response({"error": "已存在超級網管"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "超級網管密碼錯誤"}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenRefreshView):
    """/api/token/refresh/ ：改用會查 accounts.User 的序列化器。"""
    serializer_class = CustomTokenRefreshSerializer
