後端需要的 Python 套件列在 `requirements.txt`，在 NCUACG 資料夾啟用 venv 後執行：

```
pip install -r requirements.txt
```

（或直接執行 `install_modules.bat`）

AI 助理（目前未啟用）另外需要專案根目錄的 `requirements-assistant.txt`。

# 借放一下
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5), # 示例，確保有效期
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256", # 確保與 settings.py 中的 SECRET_KEY 匹配
    "SIGNING_KEY": os.getenv("JWT_SECRET_KEY"), # 確保您有 SECRET_KEY
    "VERIFY_SIGNATURE": True, # 確保驗證簽名
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",), # 確保是 Bearer
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id", # 預設是 id
    "USER_ID_CLAIM": "user_id", # 預設是 user_id
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_AUTH_HEADER_NAME": "HTTP_SLIDING_TOKEN",
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}
