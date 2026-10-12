# NCUACG/accounts/authentication.py
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings

from accounts.models import User


class CustomJWTAuthentication(JWTAuthentication):
    """
    全站的 JWT 認證（已設為 DRF 的 DEFAULT_AUTHENTICATION_CLASSES）。

    SimpleJWT 內建的 JWTAuthentication 會用 get_user_model() 去撈使用者，
    也就是 django.contrib.auth 的 User；但本專案的使用者在 accounts.User，
    所以用內建版本時，任何帶著「有效」token 的請求都會被判成 User not found → 401。
    """

    def get_user(self, validated_token):
        try:
            # 跟簽發端（RefreshToken.for_user）與續命端用同一個設定，目前是 'id'
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken("Token contained no recognizable user identification")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found", code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed("User is inactive", code="user_inactive")

        return user
