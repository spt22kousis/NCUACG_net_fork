from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.settings import api_settings
from accounts.models import User
def JWTtest(access_token):
    token = AccessToken(access_token)
    user_id = token[api_settings.USER_ID_CLAIM]
    user = User.objects.get(id=user_id)
    print(user)