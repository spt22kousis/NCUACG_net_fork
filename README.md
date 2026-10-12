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
| 歌謠祭：舊曲清單、歷屆歌單、最常播的歌 | ✅ 可用，資料從社團的 Google 試算表匯入 |
| 歌謠祭：新曲投稿、回報串、排歌組總覽、亂入曲匯入 | ✅ 可用，取代原本的回報串試算表 |
| 歌謠祭：點歌、排歌台（排場次與順序） | 🚧 建置中 |
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
│   ├── songfest/             # 歌謠祭：舊曲、歷屆播放紀錄、新曲投稿、試算表匯入
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

> 怎麼建立各種測試帳號、怎麼一步一步驗證歌謠祭功能，請看 [docs/TESTING.md](docs/TESTING.md)。

網站帳號就是後台帳號（`settings.AUTH_USER_MODEL = 'accounts.User'`），沒有第二套帳號：

- **社員**：在網站註冊、點驗證信啟用。
- **幹部**：超管在 http://localhost:8000/admin/ →「帳號」打開該社員，勾選「幹部」。之後他用同一組 email / 密碼登入 `/admin`，就能管理社課、作品、留言、活動與歌謠祭。
- **超管**：用 `createsuperuser` 建立，擁有全部權限（包括指定幹部）。

> **從 2026/10 以前的版本更新的人**：帳號資料表改版了，舊的本機資料庫不相容。請把 `NCUACG/db.sqlite3` 刪掉（或改名備份），再重新 `python manage.py migrate` 與 `createsuperuser`。

##### 歌謠祭資料（舊曲、播放紀錄）

舊曲與播放紀錄以社團的 Google 試算表為**正本**：「中央動畫社線上歌單」與「最新播放曲目統計」。網站不直接修改這兩種資料，試算表更新後再匯入一次即可（可以重複匯入，結果會跟試算表一樣）。

1. 在 Google 試算表選「檔案 → 下載 → Microsoft Excel (.xlsx)」。
2. 幹部登入 `/admin` →「歌謠祭」→「舊曲（歌單）」→ 右上角「匯入試算表」，上傳檔案。先按「試跑」看變動，再按「匯入」。

本機也可以用指令匯入：

```
python manage.py import_songfest --songlist 線上歌單.xlsx --history 最新播放曲目統計.xlsx --dry-run
```

- 過去的場次會依播放日期自動建立，名稱（例如 114下期末）是從日期推的，可以到後台「歌謠祭場次」改；之後的場次由幹部在後台新增，就會出現在歌謠祭首頁。
- 播放紀錄沒有 DVD 編號，只能用「歌曲出處 + 畫面出處 + 曲名」去對歌單；對不到的大多是沒收進歌單的新曲，播放次數照樣會算。
- 試算表含社員與投稿者資料，**不要放進 repo**。

##### 歌謠祭新曲投稿

新曲投稿取代原本的 Google 試算表回報串，規則照「歌謠祭曲目投稿規則」寫在 `NCUACG/songfest/submissions.py`。

1. 幹部在 `/admin` →「歌謠祭場次」新增這一場，填好報曲、窗歌、繳交截止時間（沒填報曲截止就不開放投稿），可以貼上出曲規定、亂入曲 Google 表單網址與說明。
2. 在同一頁下方「排歌組成員」加入主排、抄歌、播歌的帳號。排歌組不一定是幹部，加進去之後網站上就會出現「管理歌單」。
3. 社員在「新曲投稿」報曲、繳交（貼雲端連結與長度）、窗歌，並在「回報串」看大家報了什麼、閒聊。
4. 排歌組在「管理歌單」看繳交狀況與自動提醒（撞曲、撞作品、上一場播過、連曲超過 10 分鐘、繳交後改過檔案），可以延期、退件、免除罰則、匯出 CSV、複製催繳名單，並上傳亂入曲 Google 表單的回覆（.xlsx）。
5. 換歌、報曲截止後的補報這類例外，幹部到 `/admin` →「新曲投稿」直接修改。

- 罰則「下次歌謠祭禁止報曲 1 次」與亂入曲「上一場播過不入選」都以上一場大講堂歌謠祭為準，所以播放紀錄要記得匯入到最新一場。

##### 開發小提醒

- 本機沒有接 SMTP，註冊驗證信會**印在跑 Django 的終端機**上，複製裡面的 `http://localhost:5173/verify-email?token=...` 連結打開即可。
- 驗證信連結會指向 `FRONTEND_ORIGIN`（沒設就是 `http://localhost:5173`）。
- Python 套件請加進 `NCUACG/requirements.txt`，不要在 cmd 打 `pip install xxx>=1.0`：沒加引號時 `>` 會被當成輸出重導向，產生名叫 `1.0` 的垃圾檔案。
- 送出前請跑一次 `npm run lint` 與 `npm run build`（會做 TypeScript 型別檢查），後端跑 `python manage.py test accounts club event songfest`。
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

\* 社員登入：可按讚、留言、歌謠祭報曲與回報串閒聊（之後：點歌 / 參與投票）

\* 排歌組（每場在後台指定）：管理該場投稿、刪除回報串留言（之後：排歌台）

\* 幹部：可刪除任何留言、在後台管理社課、活動與歌謠祭

\* 超管：全域管理者（帳號、權限、資料）

---

#### 進度追蹤

使用 GitHub Projects + Notion 任務板進行每週進度協作。

> 最新進度請參見：\[Notion 開發進度追蹤](https://www.notion.so/216ccbce60cd8026a045e5ee044134de?v=21accbce60cd80318a00000c2a02930b\&p=222ccbce60cd80509b05cd95b25ead5b\&pm=s)

---

#### 授權條款

MIT License. All media / content assets used are for non-commercial and internal educational purposes.
