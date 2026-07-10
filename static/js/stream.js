document.addEventListener('DOMContentLoaded', function() {
    const socket = io();

    // 核心單鏡頭主控項
    let currentActiveCam = "cam_0"; // 預設看 cam_0
    const streamImg = document.getElementById('webcam-stream');
    const btnToggleStream = document.getElementById('btn-toggle-stream');
    const btnSnapshot = document.getElementById('btn-snapshot');
    const playbackCamTitle = document.getElementById('playback-cam-title');
    const camSelectorButtons = document.querySelectorAll('.cam-selector-btn');

    // 歷史回放與指標控制
    const videoListBox = document.getElementById('video-list-box');
    const playbackPlayer = document.getElementById('playback-player');
    const playerSource = document.getElementById('player-source');
    const loadingOverlay = document.getElementById('loading-overlay');
    const metricCpu = document.getElementById('metric-cpu');
    const metricRam = document.getElementById('metric-ram');
    const metricDisk = document.getElementById('metric-disk');
    const metricGpu = document.getElementById('metric-gpu');
    const gpuCardBox = document.getElementById('gpu-card-box');
    const userCount = document.getElementById('user-count');
    const metricUsers = document.getElementById('metric-users');

    // 頁籤控制項
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const matrixStreamImages = document.querySelectorAll('.matrix-stream-img');

    // 日誌稽核
    const startDateInput = document.getElementById('search-start-date');
    const endDateInput = document.getElementById('search-end-date');
    const eventTypeSelect = document.getElementById('search-event-type');
    const btnSearchLogs = document.getElementById('btn-search-logs');
    const btnExportCsv = document.getElementById('btn-export-csv');
    const auditTableBody = document.getElementById('audit-table-body');
    let currentQueriedLogs = [];

    const todayStr = new Date().toISOString().split('T')[0];
    if(startDateInput) startDateInput.value = todayStr;
    if(endDateInput) endDateInput.value = todayStr;

    // ==========================================
    // 🌟 智慧雙分頁頁籤控制切換邏輯 (頻寬效能調度)
    // ==========================================
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(targetTab).classList.add('active');
            
            if (targetTab === 'pane-matrix') {
                // 💡 巡檢矩陣分頁：切斷單畫面長連線，並重啟四格鏡頭的影像串流！
                if (streamImg) streamImg.src = "";
                matrixStreamImages.forEach(img => {
                    img.src = img.getAttribute('data-src');
                });
                console.log("🎛️ 已進入保全級四格矩陣巡檢分頁，同步解碼全頻道影像中。");
            } else if (targetTab === 'pane-single') {
                // 💡 乾淨單鏡頭分頁：摧毀四格視訊的所有連線以節省頻寬與運算資源，只恢復單個
                matrixStreamImages.forEach(img => img.src = "");
                if (streamImg && btnToggleStream && btnToggleStream.getAttribute('data-streaming') === 'true') {
                    streamImg.src = `/user_access/streaming/${currentActiveCam}?mode=smooth`;
                }
                console.log(`📹 已回到乾淨單鏡頭主控台，當前聚焦頻道: ${currentActiveCam.toUpperCase()}`);
            }
        });
    });

    // ==========================================
    // 🌟 頻道選台切换鈕功能實作
    // ==========================================
    camSelectorButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            camSelectorButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            currentActiveCam = this.getAttribute('data-cam');
            if (playbackCamTitle) playbackCamTitle.innerText = currentActiveCam.toUpperCase();
            
            // 刷新主控制台的串流網址
            if (streamImg && btnToggleStream && btnToggleStream.getAttribute('data-streaming') === 'true') {
                streamImg.src = `/user_access/streaming/${currentActiveCam}?mode=smooth`;
            }
            
            // 刷新下方回放中心的影片清單
            loadRecordingsList(currentActiveCam);
        });
    });

    // 快照動態綁定當前相機
    if (btnSnapshot) {
        btnSnapshot.addEventListener('click', () => {
            window.location.href = `/capture_snapshot/${currentActiveCam}`;
        });
    }

    // ==========================================
    // 🎬 動態載入選定攝影機的回放影片清單
    // ==========================================
    function loadRecordingsList(camId) {
        if (!videoListBox) return;
        fetch(`/recordings_list/${camId}`)
            .then(res => res.json())
            .then(data => {
                videoListBox.innerHTML = "";
                if (data.videos.length === 0) {
                    videoListBox.innerHTML = '<div style="color: #52525b; font-size: 11px; text-align: center; margin-top: 20px;">📭 該頻道目前尚無歷史錄影。</div>';
                    return;
                }
                data.videos.forEach(filename => {
                    const item = document.createElement('div');
                    item.style.padding = "5px 7px"; item.style.marginBottom = "4px";
                    item.style.background = "#18181b"; item.style.border = "1px solid #27272a";
                    item.style.borderRadius = "4px"; item.style.color = "#e4e4e7";
                    item.style.fontSize = "11px"; item.style.cursor = "pointer";
                    item.innerText = "🎬 " + filename;
                    
                    item.onmouseover = () => item.style.background = "#27272a";
                    item.onmouseout = () => item.style.background = "#18181b";
                    
                    item.addEventListener('click', function() {
                        loadingOverlay.style.display = "block";
                        fetch(`/request_playback/${camId}/${filename}`)
                            .then(res => res.json())
                            .then(result => {
                                if (result.status === "ready") {
                                    playerSource.src = result.url;
                                    playbackPlayer.load(); playbackPlayer.play();
                                }
                                loadingOverlay.style.display = "none";
                            }).catch(() => loadingOverlay.style.display = "none");
                    });
                    videoListBox.appendChild(item);
                });
            });
    }

    // ==========================================
    // 舊有 Socket.IO 數據渲染 (維持不變)
    // ==========================================
    socket.on('new_log', function(data) {
        const logConsole = document.getElementById('log-console');
        if (!logConsole) return;
        const newLog = document.createElement('div');
        newLog.style.color = (data.message.includes("警報") || data.message.includes("觸入") || data.message.includes("⚠️")) ? "#f87171" : "#4ade80";
        newLog.innerHTML = `[${new Date().toLocaleTimeString()}] ${data.message}`;
        logConsole.appendChild(newLog); logConsole.scrollTop = logConsole.scrollHeight;
    });

    socket.on('sys_metrics', function(data) {
        if (metricCpu) metricCpu.innerText = data.cpu + "%";
        if (metricRam) metricRam.innerText = data.ram + "%";
        if (metricDisk) metricDisk.innerText = data.disk_free + " GB";
        if (userCount) userCount.innerText = data.online_count;
        if (metricGpu) {
            if (data.gpu_active) {
                metricGpu.innerHTML = `<span style="color:#a855f7;">Load: ${data.gpu_load}%</span><br><span style="color:#ef4444;">Temp: ${data.gpu_temp}°C</span>`;
                gpuCardBox.style.borderColor = "#a855f7"; 
            } else {
                metricGpu.innerText = "💤 CPU 模式運作中"; gpuCardBox.style.borderColor = "#2c2c2e";
            }
        }
    });

    socket.on('update_users', function(userList) {
        if (metricUsers) { metricUsers.innerText = userList.length === 0 ? "無人連線" : userList.join(', '); metricUsers.style.color = userList.length === 0 ? "#a1a1aa" : "#a855f7"; }
    });

    // 視訊開關中斷按鈕
    if (btnToggleStream && streamImg) {
        btnToggleStream.addEventListener('click', function() {
            const isStreaming = btnToggleStream.getAttribute('data-streaming') === 'true';
            if (isStreaming) {
                streamImg.src = ""; btnToggleStream.setAttribute('data-streaming', 'false');
                btnToggleStream.innerText = "▶️ 恢復視訊畫面"; btnToggleStream.style.background = "#22c55e";
            } else {
                streamImg.src = `/user_access/streaming/${currentActiveCam}?mode=smooth`; btnToggleStream.setAttribute('data-streaming', 'true');
                btnToggleStream.innerText = "🛑 中斷視訊畫面"; btnToggleStream.style.background = "#ef4444";
            }
        });
    }

    // 歷史稽核篩選與匯出
    if (btnSearchLogs) {
        btnSearchLogs.addEventListener('click', function() {
            const start = startDateInput.value, end = endDateInput.value, type = eventTypeSelect.value;
            auditTableBody.innerHTML = '<tr><td colspan="3" style="color: #3b82f6; text-align: center; padding: 20px;">⚡ 正在檢索日誌中...</td></tr>';
            fetch(`/api/query_logs?start_date=${start}&end_date=${end}&event_type=${type}`)
                .then(res => res.json()).then(result => {
                    if (result.status === "success") {
                        currentQueriedLogs = result.data; auditTableBody.innerHTML = "";
                        if (currentQueriedLogs.length === 0) { auditTableBody.innerHTML = '<tr><td colspan="3" style="color: #71717a; text-align: center; padding: 20px;">📭 查無紀錄。</td></tr>'; return; }
                        currentQueriedLogs.forEach(log => {
                            let badgeColor = log.event_type === "FACE" ? "#ef4444" : (log.event_type === "SECURITY" ? "#a855f7" : "#3b82f6");
                            const row = document.createElement('tr');
                            row.innerHTML = `<td style="color:#e4e4e7; font-family:monospace;">${log.timestamp}</td><td><span style="background:${badgeColor}; color:white; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">${log.event_type}</span></td><td style="color:#d4d4d8;">${log.message}</td>`;
                            auditTableBody.appendChild(row);
                        });
                    }
                });
        });
    }

    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', function() {
            if (currentQueriedLogs.length === 0) { alert("❌ 請先篩選資料。"); return; }
            let csvContent = "\uFEFF🕒 時間軸,🏷️ 事件分類,💬 詳細日誌訊息\n";
            currentQueriedLogs.forEach(log => { csvContent += `${log.timestamp},${log.event_type},${log.message.replace(/,/g, "，")}\n`; });
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }), url = URL.createObjectURL(blob), link = document.createElement("a");
            link.setAttribute("href", url); link.setAttribute("download", `Report_${startDateInput.value}.csv`);
            link.style.visibility = 'hidden'; document.body.appendChild(link); link.click(); document.body.removeChild(link);
        });
    }

    // 初始載入預設相機 (cam_0) 的歷史錄影檔
    loadRecordingsList(currentActiveCam);
    const btnClearLogConsole = document.getElementById('btn-clear-log');
    if (btnClearLogConsole && logConsole) {
        btnClearLogConsole.addEventListener('click', () => {
            logConsole.innerHTML = '<div style="color: #71717a;">[SYSTEM] 面板已清除...</div>';
        });
    }
});