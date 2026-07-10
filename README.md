# 🛡️ AI Matrix Camera System (Project_AI_Matrix)

這是一個基於 Python 與 OpenCV 開發的高效能智慧多鏡頭安防監控系統。旨在提供即時影像串流、智慧硬體監控、歷史影像自動循環錄影與全方位事件日誌記錄功能。

## 🚀 核心功能 (Key Features)

* **智慧雙碼流引擎**：支援動態畫質切換（`💎 高畫質` vs `⚡ 輕量流暢`），自動調節解析度與壓縮比，適應各種網路環境。
* **工業級循環錄影**：內建 100GB 硬碟空間限制管理，系統會自動刪除最舊的錄影檔案，確保儲存空間永不爆滿。
* **即時硬體矩陣儀表板**：透過 WebSocket 即時監控 CPU、RAM、磁碟空間、網路頻寬與 GPU 加速狀態。
* **全域安防日誌**：內建全域事件記錄器，即時廣播系統操作（登入、截圖、異常）至網頁對話框。
* **安全防護門檻**：具備 Cookie-based 安全驗證機制，並支援管理員帳號記憶功能。

## 🏗️ 系統架構 (Tech Stack)

* **後端**：FastAPI, OpenCV (Video Processing), PyTorch (GPU Monitoring)
* **前端**：HTML5, CSS3 (Cyberpunk UI), JavaScript, Socket.IO
* **儲存**：SQLite (使用者認證), AVI (錄影檔案)

## 📂 目錄結構 (Directory Structure)

```text
Project_AI_Matrix/
├── camera.py           # 核心影像處理與錄影引擎
├── webcam_stream.py    # FastAPI 主程式與 Web 伺服器
├── config.py           # 系統參數與儲存路徑配置
├── storage/            # 動態數據儲存區 (自動忽略不 Git)
│   ├── recordings/     # 歷史影像紀錄
│   ├── logs/           # 安全日誌
│   └── snapshots/      # 手動快照截圖
├── templates/          # HTML 網頁模板
└── static/             # CSS 樣式與 JS 腳本

## 🛠️ 快速安裝與啟動
1. 環境準備：
確保已安裝 Python 3.9+ 並建立虛擬環境。

2. 安裝依賴：

Bash
pip install fastapi uvicorn opencv-python-headless psutil torch python-socketio Jinja2
3. 啟動系統：
執行 run_server.bat 或在終端機輸入：

Bash
python webcam_stream.py
4. 瀏覽系統：
開啟瀏覽器訪問 http://localhost:5000。

## 📜 授權與維護
本系統為客製化安防矩陣專案，所有錄影與快照存放於 storage/ 目錄。若需手動清理，請使用專案內建的 cleanup_storage.py 工具。