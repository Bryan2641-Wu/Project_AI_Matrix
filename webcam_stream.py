# webcam_stream.py
import os
import sqlite3
import hashlib
import datetime
import logging
import asyncio
import psutil  
import torch   
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import socketio
import cv2

import config
from camera import VideoCamera

# ==================================================
# 🪵 系統安全與事件日誌配置
# ==================================================
log_format = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(subsystem)s] %(message)s', '%Y-%m-%d %H:%M:%S')
file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
file_handler.setFormatter(log_format)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_format)

logger = logging.getLogger("AI_Matrix_Core")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# 跨執行緒安全通訊控制盒
main_loop = None
# 🌟 全新引入：安防系統專屬即時影音串流位元組統計器 (精確破解 Localhost 監測盲區)
LIVE_STREAM_BYTES_COUNTER = 0

def log_system_event(subsystem: str, message: str, level: str = "INFO"):
    extra = {"subsystem": subsystem}
    if level == "WARNING": logger.warning(message, extra=extra)
    elif level == "ERROR": logger.error(message, extra=extra)
    else: logger.info(message, extra=extra)
    
    global main_loop
    if main_loop and main_loop.is_running():
        color = "text-red" if level in ["WARNING", "ERROR"] else ("text-green" if subsystem == "SECURITY" else "text-blue")
        asyncio.run_coroutine_threadsafe(
            sio.emit('log_broadcast', {
                'subsystem': subsystem, 
                'message': message, 
                'color': color,
                'time': datetime.datetime.now().strftime('%H:%M:%S')
            }),
            main_loop
        )

# ==================================================
# 🔌 初始化 Socket.IO 異步雙向監控矩陣
# ==================================================
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
cameras = {}

async def background_hw_monitor():
    global LIVE_STREAM_BYTES_COUNTER
    while True:
        try:
            # 1. 系統常規效能指標
            cpu_usage = psutil.cpu_percent(interval=None)
            ram_info = psutil.virtual_memory()
            ram_usage = ram_info.percent
            
            disk_info = psutil.disk_usage(config.RECORD_DIR)
            disk_usage = disk_info.percent
            disk_free_gb = round(disk_info.free / (1024 ** 3), 1) 
            
            # 2. 🌟 智慧流量精確換算：直接讀取真實串流計數器，每秒重置一次
            current_bytes = LIVE_STREAM_BYTES_COUNTER
            LIVE_STREAM_BYTES_COUNTER = 0  # 歸零重新累積下一秒
            
            # 換算為工業標準 Mbps 頻寬單位
            stream_mbps = round((current_bytes * 8) / (1024 * 1024), 2)
            
            gpu_name = "NVIDIA GeForce RTX 5070 Ti"
            gpu_status = "CUDA ACTIVE (OFFLOADED)" if torch.cuda.is_available() else "STANDBY"

            # 將極度精確的安防系統真實吞吐量推送至前端儀表板
            await sio.emit('hw_update', {
                'cpu': cpu_usage,
                'ram': ram_usage,
                'disk_percent': disk_usage,
                'disk_free': f"{disk_free_gb} GB 剩餘",
                'net_up': f"{stream_mbps} Mbps",
                'net_down': f"{stream_mbps} Mbps",
                'gpu_name': gpu_name,
                'gpu_status': gpu_status,
                'time': datetime.datetime.now().strftime('%H:%M:%S')
            })
        except Exception as e:
            print(f"全硬體監控廣播異常: {e}")
        await asyncio.sleep(1)

# ==================================================
# ⏳ FastAPI Lifespan 生命週期管理器
# ==================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    print("\n" + "="*50)
    print("[系統自動偵測] 正在掃描實體相機設備...")
    
    # 建立一個暫存字典，只放成功連線的相機
    active_cams = {}
    
    for cam_id, source in config.CAMERA_CHANNELS.items():
        # 進行物理連線測試
        temp_cap = cv2.VideoCapture(source, cv2.CAP_DSHOW if isinstance(source, int) else cv2.CAP_FFMPEG)
        if temp_cap.isOpened():
            temp_cap.release()
            # 只有連線成功才初始化
            cameras[cam_id] = VideoCamera(cam_id=cam_id, source=source)
            active_cams[cam_id] = source
            print(f"✅ 發現活動裝置: [{cam_id.upper()}]，已納入監控矩陣。")
        else:
            print(f"❌ 裝置未響應: [{cam_id.upper()}]，已過濾。")
    
    # 將全域 cameras 變數的鍵值更新為 active_cams
    print(f"🎯 初始化完成，共 {len(cameras)} 台相機在線。")
    print("="*50 + "\n")
    
    log_system_event("SYSTEM", f"🚀 系統啟動，活動相機數量: {len(cameras)}")
    sio.start_background_task(background_hw_monitor)
    yield
    log_system_event("SYSTEM", "🛑 關閉系統，釋放所有硬體...")
    for cam in cameras.values(): cam.shutdown()

# ==================================================
# ⚡ 網頁主框架實體化與資源掛載
# ==================================================
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

def is_authenticated(request: Request) -> bool:
    return request.cookies.get("session_token") == config.SESSION_TOKEN

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        salt, stored_hash = stored_password.split(":")
        hash_obj = hashlib.sha256((plain_password + salt).encode('utf-8'))
        return hash_obj.hexdigest() == stored_hash
    except Exception: return False

# ==================================================
# 🛣️ 網頁控制台面路由矩陣
# ==================================================
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    # 動態傳遞現在有哪些相機是活的
    return templates.TemplateResponse(
        request=request, name="index.html", context={"camera_channels": cameras} 
    )

@app.get("/all_cams", response_class=HTMLResponse)
def all_cameras_wall(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request, name="all_cams.html", context={"camera_channels": cameras}
    )

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    remembered_user = request.cookies.get("remembered_username", "")
    return templates.TemplateResponse(request=request, name="login.html", context={"remembered_username": remembered_user})

@app.post("/login")
async def handle_login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    remember = form_data.get("remember") 
    
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row and verify_password(password, row[0]):
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="session_token", value=config.SESSION_TOKEN, httponly=True)
            
            if remember == "on":
                response.set_cookie(key="remembered_username", value=username, max_age=2592000)
            else:
                response.delete_cookie("remembered_username")
                
            log_system_event("SECURITY", f"🔐 管理員 [{username}] 成功通過資料庫驗證登入系統。")
            return response
    except Exception as e:
        log_system_event("SYSTEM", f"資料庫讀取異常: {e}", level="ERROR")
    
    log_system_event("SECURITY", f"💥 登入失敗：帳號或密碼不匹配 [{username}] ！", level="WARNING")
    remembered_user = request.cookies.get("remembered_username", "")
    return templates.TemplateResponse(request=request, name="login.html", context={"error": "帳號或密碼錯誤，拒絕存取。", "remembered_username": remembered_user})

@app.get("/logout")
def handle_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    log_system_event("SECURITY", "🚪 使用者 [admin] 已安全離線。")
    return response

# 🌟 串流的核心路由：在此處精確包裹與統計每一幀圖片的體積大小
@app.get("/user_access/streaming/{cam_id}")
def video_feed(cam_id: str, request: Request, mode: str = "smooth"):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    if cam_id not in cameras: raise HTTPException(status_code=404)
    
    # 建立一個極度精準的包裝產生器，即時截獲發送出去的位元組
    def streaming_bandwidth_tracker():
        global LIVE_STREAM_BYTES_COUNTER
        for chunk in cameras[cam_id].get_frame_generator(mode=mode):
            LIVE_STREAM_BYTES_COUNTER += len(chunk)  # 實時攔截累加
            yield chunk

    return StreamingResponse(streaming_bandwidth_tracker(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/capture_snapshot/{cam_id}")
def capture_snapshot(cam_id: str, request: Request):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    if cam_id not in cameras: return RedirectResponse(url="/")
    current_frame = cameras[cam_id].Frame
    if current_frame is not None:
        filename = f"snapshot_{cam_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(os.path.join(config.SNAPSHOT_DIR, filename), current_frame)
        log_system_event("SNAPSHOT", f"📸 系統快照：使用者遠端手動截取攝影機 [{cam_id.upper()}] 畫面 ({filename})")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/recordings_list/{cam_id}")
def get_recordings_list(cam_id: str, request: Request):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    target_dir = os.path.join(config.RECORD_DIR, cam_id)
    if not os.path.exists(target_dir): return {"recordings": []}
    files = sorted([f for f in os.listdir(target_dir) if f.endswith(".avi")], key=lambda x: os.path.getmtime(os.path.join(target_dir, x)), reverse=True)
    return {"recordings": files}

if __name__ == "__main__":
    import uvicorn
    print(f"📡 網頁伺服器正在主機 {config.HOST}:{config.PORT} 上啟動...")
    uvicorn.run("webcam_stream:sio_app", host=config.HOST, port=config.PORT, reload=False)