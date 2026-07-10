// ==========================================
// 🚀 2026 前端即時通訊與多鏡頭矩陣控制邏輯
// ==========================================

// 初始化雙向即時聯動通訊
const socket = io();

// 1. 監聽伺服器廣播的系統硬體與 GPU 指標
socket.on('sys_metrics', function(data) {
    document.getElementById('cpu-val').innerText = data.cpu + '%';
    document.getElementById('ram-val').innerText = data.ram + '%';
    document.getElementById('disk-val').innerText = data.disk_free + ' GB';
    document.getElementById('online-count').innerText = data.online_count;
    
    if(data.gpu_active) {
        document.getElementById('gpu-load-val').innerText = data.gpu_load + '%';
        document.getElementById('gpu-temp-val').innerText = data.gpu_temp + '°C';
    } else {
        document.getElementById('gpu-load-val').innerText = 'N/A';
        document.getElementById('gpu-temp-val').innerText = 'N/A';
    }
});

// 2. 監聽背景 AI 觸發的最新日誌事件並置底滾動
socket.on('new_log', function(data) {
    const consoleBox = document.getElementById('log-console');
    const newLine = document.createElement('div');
    const timeStr = new Date().toLocaleTimeString();
    
    newLine.className = 'log-line';
    // 智慧偵測帶有警告符號的文字，動態變更著色
    if(data.message.includes('⚠️') || data.message.includes('🚨') || data.message.includes('警報')) {
        newLine.classList.add('log-alert');
    } else {
        newLine.classList.add('log-info');
    }
    
    newLine.innerText = `[${timeStr}] ${data.message}`;
    consoleBox.appendChild(newLine);
    consoleBox.scrollTop = consoleBox.scrollHeight; // 自動向下滾動
});

// 3. 頻道高畫質 / 流暢模式動態切換
function changeMode(camId, mode) {
    const streamImg = document.getElementById(`stream-${camId}`);
    if (streamImg) {
        // 動態變更串流路徑與參數，通知後端 OpenCV 變更解析度與壓縮比
        streamImg.src = `/user_access/streaming/${camId}?mode=${mode}`;
    }
}

// 4. 點擊畫面放大 / 縮小巡檢功能
function toggleExpand(camId) {
    const box = document.getElementById(`box-${camId}`);
    if (box) {
        box.classList.toggle('expanded');
    }
}

// 5. 拉取並更新選定相機的歷史封裝影片列表
function loadRecordingsList() {
    const camId = document.getElementById('cam-select').value;
    const ul = document.getElementById('recording-ul');
    ul.innerHTML = '<li class="list-placeholder">正在檢索資料夾...</li>';
    
    fetch(`/recordings_list/${camId}`)
        .then(res => res.json())
        .then(data => {
            ul.innerHTML = '';
            if (data.videos.length === 0) {
                ul.innerHTML = '<li class="list-placeholder">⚠️ 目前暫無已封裝好的歷史錄影</li>';
                return;
            }
            data.videos.forEach(filename => {
                const li = document.createElement('li');
                li.innerText = `🎬 ${filename}`;
                li.onclick = () => startPlayback(camId, filename);
                ul.appendChild(li);
            });
        })
        .catch(() => {
            ul.innerHTML = '<li class="list-placeholder">❌ 連線失敗</li>';
        });
}

// 6. 點擊影片觸發 NVIDIA 獨立顯卡加速轉碼並播放
function startPlayback(camId, filename) {
    const windowBox = document.getElementById('playback-window');
    const player = document.getElementById('player');
    
    windowBox.style.display = 'block';
    player.innerHTML = ''; // 清空播放器舊源
    
    // 向後端請求硬體解碼與切片轉碼路徑
    fetch(`/request_playback/${camId}/${filename}`)
        .then(res => {
            if (res.status === 404) throw new Error('檔案未就緒');
            return res.json();
        })
        .then(data => {
            if (data.status === 'ready') {
                player.src = data.url;
                player.load();
                player.play();
            }
        })
        .catch(err => {
            alert('⚠️ 顯卡轉碼引擎正在忙碌中或檔案尚未封裝完成，請稍後再試！');
        });
}

// 頁面初次渲染完成後，自動拉取第一個相機的歷史清單
window.onload = function() {
    if (document.getElementById('cam-select')) {
        loadRecordingsList();
    }
};