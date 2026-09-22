"""
URL configuration for NCUACG project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# NCUACG/urls.py
from django.contrib import admin
from django.urls import path, include
from accounts.views import (
    LoginView, LogoutView, RegisterView, GetCaptcha,
    VerifyRegistrationView, UserProfileView, CustomTokenRefreshView,
)

urlpatterns = [
    path("api/get-captcha/", GetCaptcha.as_view(), name="get_captcha"),
    path("api/login/", LoginView.as_view(), name="login"),
    path("api/logout/", LogoutView.as_view(), name="api-logout"),
    path("admin/", admin.site.urls),
    # ★ 把 assistant 掛到 /api/assistant/ 之下
    # path("api/assistant/", include("assistant.urls")),
    path('api/register/', RegisterView.as_view(), name='register_user'),
    path('api/captcha/', include('captcha.urls')),
    path("api/verify-registration/", VerifyRegistrationView.as_view(), name="verify_registration"),
    path('api/me/', UserProfileView.as_view(), name='me'),
    # Access token 過期時由前端攔截器自動續命
    path("api/token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    # 活動公告
    path("api/event/", include("event.urls")),
]
