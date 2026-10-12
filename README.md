### NCU ACG 社團網站｜NCU ACG Club Website

中央大學動畫社專屬平台，整合社團介紹、活動公告、歌謠祭資料平台、AI 助理等功能，打造專屬於動漫愛好者的互動空間。

---

#### 功能與進度

| 功能 | 狀態 |
| --- | --- |
| 首頁（開場動畫、最新公告、關於社團） | ✅ 可用，支援手機 |
| 社課介紹（各社課簡介） | ✅ 可用，介紹文字由各社課負責人撰寫 |
| 成果牆（作品、按讚、留言） | ✅ 可用，作品目前由幹部在 Django admin 上架 |
| 活動公告 | ✅ 可用，活動由幹部在 Django admin 新增 |
| 註冊 / 登入 / 信箱驗證 / 重寄驗證信 | ✅ 可用 |
| 忘記密碼 | 🚧 尚未接上後端 |
| 行事曆 | 🚧 建置中 |
| 歌謠祭平台（點歌、投稿、排行榜、排歌後台） | 🚧 建置中 |
| 生成式 AI 助理 | 🛠️ 維護中（後端 assistant app 未啟用） |

---

#### 技術架構

- 前端：React 19 + TypeScript + Vite（`frontend/`）
- 後端：Django + Django REST Framework + SimpleJWT（`NCUACG/`）
- 資料庫：SQLite（開發用）
- 前後端分離：前端所有請求都走 `/api`，開發時由 Vite proxy 轉給 `http://localhost:8000`

---

#### 專案結構

```
NCUACG_net/
├── .envExample.md            # 後端 .env 範本與說明
├── requirements-assistant.txt  # AI 助理額外需要的套件（目前未啟用）
├── NCUACG/                   # Django 後端（manage.py 在這層）
│   ├── NCUACG/               # 設定：settings.py、urls.py
│   ├── accounts/             # 帳號：註冊、登入、信箱驗證、JWT
│   ├── club/                 # 社課與成果牆：社課、作品、按讚、留言
│   ├── event/                # 活動公告
│   ├── assistant/            # AI 助理（目前未掛載）
│   ├── home/                 # 預留
│   ├── requirements.txt      # 後端必要套件
│   └── install_modules.bat   # Windows 一鍵安裝套件
└── frontend/                 # React 前端
    ├── vite.config.ts        # 開發伺服器與 /api、/media proxy
    └── src/
        ├── api/client.ts     # 全站唯一的 HTTP 出口（自動帶 token、過期自動續命）
        ├── config.ts         # API 位址、功能開關
        ├── contexts/         # 登入狀態、AI 助理狀態
        ├── components/       # 首頁區塊、側邊欄、公告欄等共用元件
        ├── pages/            # 各頁面
        ├── styles/           # 各頁面 CSS（*-mobile.css 為手機版覆寫）
        └── data/             # 靜態資料（社課介紹、關於社團、公告備援）
```

---

#### 開發環境

需要 Python 3.12 以上與 Node.js 20 以上。

##### 1. 後端

```
cd NCUACG
python -m venv venv
venv\Scripts\activate            # macOS / Linux：source venv/bin/activate
pip install -r requirements.txt
```

建立 `NCUACG/.env`（跟 `manage.py` 同一層），內容照 [.envExample.md](.envExample.md)，至少要有 `DJANGO_SECRET_KEY` 與 `DJANGO_DEBUG=True`。

```
python manage.py migrate
python manage.py createsuperuser   # 建立超管帳號（用 email 登入，網站與 /admin 共用）
python manage.py runserver
```

Windows 也可以直接執行專案根目錄的 `runserver.bat`。

##### 2. 前端

```
cd frontend
npm install
npm run dev
```

打開 http://localhost:5173 。前端的 `/api`、`/media` 會自動轉給本機的 Django（見 `vite.config.ts`），不需要另外設定網址。

##### 帳號與幹部

網站帳號就是後台帳號（`settings.AUTH_USER_MODEL = 'accounts.User'`），沒有第二套帳號：

- **社員**：在網站註冊、點驗證信啟用。
- **幹部**：超管在 http://localhost:8000/admin/ →「帳號」打開該社員，勾選「幹部」。之後他用同一組 email / 密碼登入 `/admin`，就能管理社課、作品、留言與活動。
- **超管**：用 `createsuperuser` 建立，擁有全部權限（包括指定幹部）。

> **從 2026/10 以前的版本更新的人**：帳號資料表改版了，舊的本機資料庫不相容。請把 `NCUACG/db.sqlite3` 刪掉（或改名備份），再重新 `python manage.py migrate` 與 `createsuperuser`。

##### 開發小提醒

- 本機沒有接 SMTP，註冊驗證信會**印在跑 Django 的終端機**上（內容是 base64，解開後就是驗證連結）。
- 驗證信連結會指向 `FRONTEND_ORIGIN`（沒設就是 `http://localhost:5173`）。
- Python 套件請加進 `NCUACG/requirements.txt`，不要在 cmd 打 `pip install xxx>=1.0`：沒加引號時 `>` 會被當成輸出重導向，產生名叫 `1.0` 的垃圾檔案。
- 送出前請跑一次 `npm run lint` 與 `npm run build`（會做 TypeScript 型別檢查），後端跑 `python manage.py test accounts club event`。
- GitHub Actions（`.github/workflows/ci.yml`）會在每次 push 到 main 與每個 PR 自動跑上面這些檢查。

---

#### 團隊成員與分工

PM / 文件：元風，負責規格整合、時程規劃、Notion 文件管理

前端：夜閃、影蒙，負責首頁切版、導覽列元件、互動樣式

後端：元風、夜閃、能量、主推，負責 Django 架構、登入機制、資料串接、API 建置

UI/UX：可可，負責視覺設計、Figma 產出、元件命名風格

多媒體與動畫：主推、能量，負責 loading 動畫、動畫呈現（SVG / Lottie）

資料與內容管理：影蒙，負責 Markdown 轉檔、歌曲資料轉存、格式統整

---

#### 權限分級（簡要）

\* 一般訪客：可瀏覽首頁、社課、活動頁、成果牆

\* 社員登入：可按讚、留言（之後：點歌 / 投稿 / 參與投票）

\* 幹部 / 排歌組：可刪除任何留言（之後：進入後台編輯歌單與排序）

\* 超管：全域管理者（帳號、權限、資料）

---

#### 進度追蹤

使用 GitHub Projects + Notion 任務板進行每週進度協作。

> 最新進度請參見：\[Notion 開發進度追蹤](https://www.notion.so/216ccbce60cd8026a045e5ee044134de?v=21accbce60cd80318a00000c2a02930b\&p=222ccbce60cd80509b05cd95b25ead5b\&pm=s)

---

#### 授權條款

MIT License. All media / content assets used are for non-commercial and internal educational purposes.
