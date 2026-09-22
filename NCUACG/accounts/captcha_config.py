import random
import string

def alnum_challenge(length=5):
    # 圖片上會顯示大小寫混合的字元，但 django-simple-captcha 存檔時會把答案轉小寫，
    # 登入時也用小寫比對，所以使用者輸入「不分大小寫」。
    # （原本叫 alnum_case_sensitive，名稱與實際行為不符，已改名）
    chars = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    text = ''.join(random.choice(chars) for _ in range(length))
    return text, text