# 社課介紹 + 成果牆 MVP

End date: 08/18/2025
Start value: 20
End value: 100
Progress: 20%
Priority: Medium
Assignee: HoneyLemon , 陳 可烜, 主推, ルネッサンス 
Status: In progress

### About project

- 撰寫社課簡介元件格式
- 成果牆設計元件與欄位、模擬一筆資料作測試
- 彙整資料樣板與輸入模板

### Action items

- [ ]  社課介紹頁：`/club/` 能顯示至少 3 種社課（剪輯 / 繪圖 / TRPG）之卡片，簡介、連結「查看成果」
- [ ]  成果牆頁：`/club/works/` 能網格顯示 6 筆假作品（縮圖 + 標題 + 製作者）
- [ ]  模板分離：共用 `club/base_club.html`，頁面內容用 `{% block content %}` 注入
- [x]  假資料來源：假資料 JSON 或硬寫在 `views.py`（後端製造 `context` 傳給 template）
- [ ]  樣式統一：使用 `static/css/club.css`；RWD 至少平板斷點無跑版

### Documents

[https://www.notion.so](https://www.notion.so)