import os
import time
import datetime
import threading
import cv2
import numpy as np
import config

class VideoCamera:
    def __init__(self, cam_id, source, shared_model=None):
        self.cam_id = cam_id
        self.source = source
        # 即使傳入 shared_model 也直接忽略，完全去 YOLO 化
        self.model = None 
        
        # 建立專屬該頻道的影像儲存目錄
        self.cam_record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.cam_record_dir, exist_ok=True)
        
        # 執行緒與運行狀態控制指標
        self.Frame = None
        self.is_running = True
        self.current_record_file = None
        
        # 初始化實體/網路攝影機
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if isinstance(self.source, int) else cv2.CAP_FFMPEG)
        
        # 動態校準硬體真實解析度與影格率 (FPS)
        if self.cap.isOpened():
            self.real_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.real_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.real_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # 防呆機制：若部分 WebCam 回傳的 FPS 為 0 或異常，自動給予工業標準 20.0 預設值
            if self.real_fps <= 0 or self.real_fps > 60:
                self.real_fps = 20.0
        else:
            # 線路未掛載時的降級黑畫面尺寸預設值
            self.real_width = 640
            self.real_height = 480
            self.real_fps = 20.0

        # 初始化錄影寫入器組件 (VideoWriter)
        self.out = None
        self._init_next_video_writer()
        
        # 發動獨立背景錄影與畫面拉取執行緒
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _init_next_video_writer(self):
        """建立防斷電、具備動態尺寸校準的錄影檔案寫入器"""
        if self.out is not None:
            self.out.release()
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{self.cam_id}_{timestamp}.avi"
        self.current_record_file = os.path.join(self.cam_record_dir, filename)
        
        # 使用 XVID 編碼器封裝 .avi 檔
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        
        # 使用與硬體實體 100% 咬合的真寬高與真 FPS 進行宣告，消滅寫影格錯誤
        self.out = cv2.VideoWriter(
            self.current_record_file, 
            fourcc, 
            self.real_fps, 
            (self.real_width, self.real_height)
        )
        self.last_split_time = time.time()

    def _capture_worker(self):
        """獨立的守護執行緒：負責拉流並即時寫入 AVI 檔案"""
        while self.is_running:
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                # 🛡️ 訊號中斷防護：建立一個與規格尺寸相同的純黑防護影格，維持串流不中斷
                frame = np.zeros((self.real_height, self.real_width, 3), dtype=np.uint8)
                cv2.putText(
                    frame, 
                    f"CHANNEL [{self.cam_id.upper()}] NO SIGNAL", 
                    (int(self.real_width*0.1), int(self.real_height*0.5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

            # 💾 直接寫入背景防斷電錄影檔（不經過任何 AI 延遲，速度極快）
            if self.out is not None:
                self.out.write(frame)
                
            # 將當前最新的一影格拋給前端 Socket.IO / Streaming 進行廣播
            self.Frame = frame
            
            # ⏰ 每隔一小時自動切片封裝一次影片，防止檔案過大損壞
            if time.time() - self.last_split_time > 3600:
                self._init_next_video_writer()

            # 依據攝影機的真實影格率進行精確的延時調配，防止執行緒暴走榨乾 CPU
            elapsed = time.time() - start_time
            sleep_duration = max(0.001, (1.0 / self.real_fps) - elapsed)
            time.sleep(sleep_duration)

    def get_frame_generator(self, mode="smooth"):
        """網頁前端串流分發器：配合 FastAPI StreamingResponse 輸出"""
        encode_quality = 85 if mode == "high" else 60
        
        while self.is_running:
            if self.Frame is None:
                time.sleep(0.05)
                continue
                
            # 將 OpenCV 的 BGR 矩陣編碼為輕量化 .jpg
            ret, jpeg = cv2.imencode('.jpg', self.Frame, [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality])
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            
            time.sleep(0.04 if mode == "smooth" else 0.06)

    def shutdown(self):
        """安全釋放硬體與寫入器資源"""
        self.is_running = False
        if self.cap.isOpened():
            self.cap.release()
        if self.out is not None:
            self.out.release()