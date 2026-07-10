# camera.py
import os
import time
import datetime
import threading
import cv2
import numpy as np
import config

class VideoCamera:
    def __init__(self, cam_id, source, shared_model=None):
        """
        初始化個別相機頻道
        :param cam_id: 相機識別代號 (如 'cam_0') -> 用於建立對應資料夾與命名錄影檔
        :param source: 訊號源 (如 0, 1, 2 代表 USB 鏡頭) -> 供 OpenCV 的 VideoCapture 讀取
        """
        self.cam_id = cam_id
        self.source = source
        self.model = None  # 徹底去 YOLO AI 化，回歸純 OpenCV 極速架構
        
        # 1. 動態建立該頻道專屬的錄影儲存路徑 (如 storage/recordings/cam_0)
        self.cam_record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.cam_record_dir, exist_ok=True)
        
        # 2. 狀態控制指標
        self.Frame = None          # 存放當前最新的一影格 (供前端手動快照與即時串流拉取)
        self.is_running = True     # 控制背景執行緒運作開關
        self.current_record_file = None
        
        # 3. 初始化實體鏡頭 (Windows 下實體鏡頭使用 CAP_DSHOW 驅動防卡死)
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if isinstance(self.source, int) else cv2.CAP_FFMPEG)
        
        # 🌟 核心防護：動態校準硬體的真實寬高與 FPS，徹底消滅 Failed to write frame 洗版警告
        if self.cap.isOpened():
            self.real_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.real_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.real_fps = self.cap.get(cv2.CAP_PROP_FPS)
            # 防呆：若 WebCam 硬體回傳的 FPS 異常，自動給予工業標準 20.0 預設值
            if self.real_fps <= 0 or self.real_fps > 60:
                self.real_fps = 20.0
        else:
            # 鏡頭未掛載時的降級安全預設尺寸
            self.real_width, self.real_height, self.real_fps = 640, 480, 20.0

        # 4. 啟動防斷電歷史錄影寫入器
        self.out = None
        self._init_next_video_writer()
        
        # 5. 發動獨立守護執行緒 (Thread)，讓拉流、錄影在背景全速奔跑，絕不卡死網頁主程式
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _init_next_video_writer(self):
        """建立具備動態硬體尺寸校準的 AVI 錄影檔案寫入器"""
        if self.out is not None:
            self.out.release()  # 釋放舊的寫入器關閉舊檔案
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{self.cam_id}_{timestamp}.avi"
        self.current_record_file = os.path.join(self.cam_record_dir, filename)
        
        # 使用標準 XVID 編碼器封裝 .avi 檔
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        
        # 🌟 這裡使用的寬高與 FPS 必須與硬體完全 100% 咬合，否則 FFmpeg 會拒絕寫入
        self.out = cv2.VideoWriter(
            self.current_record_file, fourcc, self.real_fps, (self.real_width, self.real_height)
        )
        self.last_split_time = time.time()

    def _capture_worker(self):
        """背景核心守護執行緒：負責不間斷拉取影像流並即時寫入 AVI 檔案"""
        while self.is_running:
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                # 🛡️ 訊號中斷防護：若鏡頭被拔除，自動建立同尺寸的純黑防護影格，維持監控大螢幕不崩潰
                frame = np.zeros((self.real_height, self.real_width, 3), dtype=np.uint8)
                cv2.putText(
                    frame, f"CHANNEL [{self.cam_id.upper()}] NO SIGNAL", 
                    (int(self.real_width*0.1), int(self.real_height*0.5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

            # 💾 影像無延遲，直接寫入背景防斷電錄影檔
            if self.out is not None:
                self.out.write(frame)
                
            # 將最新影格刷新到記憶體中，供外面的 webcam_stream.py 隨時拿去給前端看
            self.Frame = frame
            
            # ⏰ 每隔一小時自動切片封裝一次影片，防止單一檔案過大損壞
            if time.time() - self.last_split_time > 3600:
                self._init_next_video_writer()

            # 依據硬體的真實影格率進行精確的延時調配，防止無限迴圈榨乾 CPU
            elapsed = time.time() - start_time
            sleep_duration = max(0.001, (1.0 / self.real_fps) - elapsed)
            time.sleep(sleep_duration)

    def get_frame_generator(self, mode="smooth"):
        """網頁前端 MJPEG 串流分發器 (配合 FastAPI StreamingResponse 輸出)"""
        # 依據前端選擇的模式動態調配 JPEG 壓縮率，兼顧畫質與頻寬優化
        encode_quality = 85 if mode == "high" else 60
        
        while self.is_running:
            if self.Frame is None:
                time.sleep(0.05)
                continue
                
            # 將內部的 BGR 矩陣編碼為輕量化 .jpg 二進位流
            ret, jpeg = cv2.imencode('.jpg', self.Frame, [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality])
            if not ret:
                continue
                
            # 包裝成工業推播標準格式傳給前端 img 標籤
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            
            time.sleep(0.04 if mode == "smooth" else 0.06)

    def shutdown(self):
        """當系統 lifespan 結束時，安全關閉並釋放硬體硬碟資源"""
        self.is_running = False
        if self.cap.isOpened(): 
            self.cap.release()
        if self.out is not None: 
            self.out.release()