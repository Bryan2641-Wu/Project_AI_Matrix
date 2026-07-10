import os
import threading
import time
import datetime
import cv2
import config
from ultralytics import YOLO

class VideoCamera:
    def __init__(self, cam_id, cam_source, shared_yolo):
        self.cam_id = cam_id
        self.camera = cv2.VideoCapture(cam_source, cv2.CAP_DSHOW) if isinstance(cam_source, int) else cv2.VideoCapture(cam_source)
        
        self.Frame = None
        self.status = False
        self.is_stop = False
        self.current_mode = None
        self.jpeg_quality = 85
        
        self.video_writer = None
        self.current_record_file = ""
        self.segment_start_time = 0
        
        self.model = shared_yolo
        self.last_alert_time = 0      
        self.alert_cooldown = 10       
        
        self.record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.record_dir, exist_ok=True)
        
        threading.Thread(target=self._query_and_record, daemon=True).start()

    def _query_and_record(self):
        while not self.is_stop:
            if self.camera.isOpened():
                self.status, frame = self.camera.read()
                if self.status:
                    annotated_frame = self._process_ai_detection(frame)
                    self.Frame = annotated_frame
                    self._handle_recording(annotated_frame)
            time.sleep(0.033) 
        self._stop_video_writer()

    def _process_ai_detection(self, frame):
        try:
            img = frame.copy()
            # 🌟 透過 ONNX 引擎進行超高速 GPU 推理
            results = self.model(img, verbose=False)
            person_detected = False
            best_conf = 0.0  
            
            for result in results:
                for box in result.boxes:
                    if int(box.cls[0]) == 0: # person
                        person_detected = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        if conf > best_conf: best_conf = conf  
                        
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(img, f"[{self.cam_id.upper()}] Person: {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if person_detected:
                current_time = time.time()
                if current_time - self.last_alert_time > self.alert_cooldown:
                    self.last_alert_time = current_time
                    time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"ai_{self.cam_id}_{time_str}.jpg"
                    filepath = os.path.join(config.SNAPSHOT_DIR, filename)
                    cv2.imwrite(filepath, img)
                    
                    from webcam_stream import log_system_event
                    # 🌟 這裡日誌訊息故意帶有「⚠️」與「警報」，方便前端捕捉變色
                    log_system_event("FACE", f"⚠️ [AI 警報] 攝影機 [{self.cam_id.upper()}] 偵測到人類闖入！關鍵影格已存檔 ({filename}，信心度: {best_conf:.2f})", filepath=filepath)
            return img
        except Exception:
            return frame

    def _cleanup_old_recordings(self):
        try:
            while True:
                files = [os.path.join(self.record_dir, f) for f in os.listdir(self.record_dir) if f.endswith('.avi')]
                total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
                if total_size <= (config.MAX_RECORD_SIZE_BYTES // len(config.CAMERA_LIST)): break
                files.sort(key=lambda x: os.path.getmtime(x))
                if files:
                    oldest_file = files[0]
                    if oldest_file == self.current_record_file: break
                    from webcam_stream import log_system_event
                    log_system_event("STORAGE", f"⚠️ [容量維護] 攝影機 [{self.cam_id.upper()}] 自動覆蓋最舊影片: {os.path.basename(oldest_file)}")
                    os.remove(oldest_file)
                else: break
        except Exception: pass

    def _handle_recording(self, frame):
        now = time.time()
        if self.video_writer is None or (now - self.segment_start_time) >= config.RECORD_SEGMENT_SECONDS:
            self._stop_video_writer()
            self._cleanup_old_recordings()
            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rec_{self.cam_id}_{time_str}.avi"
            filepath = os.path.join(self.record_dir, filename)
            self.current_record_file = filepath
            h, w, _ = frame.shape
            self.video_writer = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'XVID'), 30.0, (w, h))
            self.segment_start_time = now
            from webcam_stream import log_system_event
            log_system_event("SYSTEM", f"🎬 [{self.cam_id.upper()}] 開始錄製防斷電監控檔案: {filename}")
        if self.video_writer is not None:
            self.video_writer.write(frame)

    def _stop_video_writer(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

    def set_mode(self, mode):
        if self.current_mode == mode: return self.jpeg_quality
        if mode == 'high':
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.HIGH_MODE_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.HIGH_MODE_HEIGHT)
            self.jpeg_quality = config.HIGH_MODE_QUALITY
        else:
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.SMOOTH_MODE_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SMOOTH_MODE_HEIGHT)
            self.jpeg_quality = config.SMOOTH_MODE_QUALITY
        self.current_mode = mode
        return self.jpeg_quality

    def get_frame_generator(self, mode):
        self.set_mode(mode)
        target_fps = 24 if mode == 'high' else 30
        frame_duration = 1.0 / target_fps
        while True:
            start_time = time.time()
            if self.Frame is None:
                time.sleep(0.01)
                continue
            ret, buffer = cv2.imencode('.jpg', self.Frame.copy(), [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            sleep_time = frame_duration - (time.time() - start_time)
            if sleep_time > 0: time.sleep(sleep_time)

    def shutdown(self):
        self.is_stop = True
        self._stop_video_writer()
        if self.camera.isOpened(): self.camera.release()