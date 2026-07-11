# camera.py
import os
import time
import datetime
import threading
import cv2
import numpy as np
import config

class VideoCamera:
    def __init__(self, cam_id, source):
        """
        初始化個別相機頻道 (高質感 OSD 時間戳安防版)
        """
        self.cam_id = cam_id
        self.source = source
        
        # 1. 建立錄影儲存路徑
        self.cam_record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.cam_record_dir, exist_ok=True)
        
        # 2. 狀態指標
        self.Frame = None          
        self.is_running = True     
        self.current_record_file = None
        
        # 3. 初始化鏡頭
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if isinstance(self.source, int) else cv2.CAP_FFMPEG)
        
        if self.cap.isOpened():
            self.real_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.real_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.real_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.real_fps <= 0 or self.real_fps > 60: self.real_fps = 20.0
        else:
            self.real_width, self.real_height, self.real_fps = 640, 480, 20.0

        # 4. 初始化錄影
        self.out = None
        self._init_next_video_writer()
        
        # 5. 啟動背景守護執行緒
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _enforce_storage_limit(self, limit_gb=100):
        """循環錄影機制：超過 100GB 自動覆蓋最舊檔案"""
        limit_bytes = limit_gb * 1024 * 1024 * 1024
        all_files = []
        for root, dirs, files in os.walk(config.RECORD_DIR):
            for file in files:
                if file.endswith(".avi"):
                    path = os.path.join(root, file)
                    try: all_files.append((path, os.path.getmtime(path), os.path.getsize(path)))
                    except: continue
        
        all_files.sort(key=lambda x: x[1])
        total_size = sum(x[2] for x in all_files)
        
        while total_size > limit_bytes and all_files:
            oldest_file = all_files.pop(0)
            try:
                os.remove(oldest_file[0])
                total_size -= oldest_file[2]
                print(f"⚠️ 空間已達上限 ({limit_gb}GB)，執行循環覆蓋：已自動刪除最舊影片 {oldest_file[0]}")
            except Exception as e:
                print(f"清理檔案失敗: {e}")

    def _init_next_video_writer(self):
        """建立寫入器並執行空間檢查"""
        self._enforce_storage_limit(limit_gb=100) 
        
        if self.out is not None: self.out.release()  
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{self.cam_id}_{timestamp}.avi"
        self.current_record_file = os.path.join(self.cam_record_dir, filename)
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.out = cv2.VideoWriter(
            self.current_record_file, fourcc, self.real_fps, (self.real_width, self.real_height)
        )
        self.last_split_time = time.time()

    def _capture_worker(self):
        """背景核心執行緒：負責拉取畫面、烙印極簡高質感時間戳、寫入硬碟檔"""
        while self.is_running:
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                frame = np.zeros((self.real_height, self.real_width, 3), dtype=np.uint8)
                cv2.putText(
                    frame, f"CHANNEL [{self.cam_id.upper()}] NO SIGNAL", 
                    (int(self.real_width*0.1), int(self.real_height*0.5)),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (80, 80, 240), 1, cv2.LINE_AA
                )
            else:
                # 🌟 核心升級：精緻化 OSD 浮水印（專業半透明黑底白字襯條）
                timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                display_text = f"● {self.cam_id.upper()}   {timestamp_str}"
                
                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 0.45
                thickness = 1
                
                # 動態精確計算文字長寬，以此動態生成地墊背板
                text_size, _ = cv2.getTextSize(display_text, font, font_scale, thickness)
                text_w, text_h = text_size
                
                # 建立疊加層實作 60% 半透明極簡黑（Tech Black）背景塊
                overlay = frame.copy()
                pad_x, pad_y = 15, 12
                start_point = (15, 15)
                end_point = (15 + text_w + pad_x, 15 + text_h + pad_y)
                
                cv2.rectangle(overlay, start_point, end_point, (24, 24, 28), -1)
                alpha = 0.65  # 襯底不透明度
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                
                # 繪製高雅科技純白文字（Off-White）
                text_position = (15 + int(pad_x/2), 15 + text_h + int(pad_y/2) - 1)
                cv2.putText(frame, display_text, text_position, font, font_scale, (245, 245, 245), thickness, cv2.LINE_AA)
            
            if self.out is not None: self.out.write(frame)
            self.Frame = frame
            
            if time.time() - self.last_split_time > 3600:
                self._init_next_video_writer()

            elapsed = time.time() - start_time
            time.sleep(max(0.001, (1.0 / self.real_fps) - elapsed))

    def get_frame_generator(self, mode="smooth"):
        """雙碼流轉碼器：根據模式調整解析度與品質"""
        while self.is_running:
            if self.Frame is None:
                time.sleep(0.05)
                continue
                
            if mode == "high":
                out_frame = self.Frame.copy()
                encode_quality = 95
                delay = 0.02
            else:
                h, w = self.Frame.shape[:2]
                scale = 400 / w if w > 400 else 1.0
                out_frame = cv2.resize(self.Frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                encode_quality = 30
                delay = 0.04

            ret, jpeg = cv2.imencode('.jpg', out_frame, [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality])
            if not ret: continue
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            time.sleep(delay)

    def shutdown(self):
        self.is_running = False
        if self.cap.isOpened(): self.cap.release()
        if self.out is not None: self.out.release()