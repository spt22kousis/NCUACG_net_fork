@echo off
REM 在 NCUACG 資料夾執行，並先啟用 venv。
REM 注意：不要把 pip 套件寫成 pip xxx>=1.0 這種形式，cmd 會把 > 當成輸出重導向，
REM 結果是在資料夾裡產生名叫 1.0 的檔案（先前 repo 裡的 0.9.0、3.15.0 就是這樣來的）。
cd /D "%~dp0"
pip install -r requirements.txt
pause
