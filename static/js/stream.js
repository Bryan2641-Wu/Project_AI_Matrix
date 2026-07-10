// static/js/stream.js
const socket = io();

function changeMode(camId, mode) {
    const streamImg = document.getElementById(`stream-${camId}`);
    if (streamImg) streamImg.src = `/user_access/streaming/${camId}?mode=${mode}`;
}

function toggleExpand(camId) {
    const box = document.getElementById(`box-${camId}`);
    if (box) box.classList.toggle('expanded');
}

function loadRecordingsList() {
    const camId = document.getElementById('cam-select').value;
    const ul = document.getElementById('recording-ul');
    ul.innerHTML = '<li class="list-placeholder">正在檢索資料夾...</li>';
    
    fetch(`/recordings_list/${camId}`)
        .then(res => res.json())
        .then(data => {
            ul.innerHTML = '';
            if (!data.recordings || data.recordings.length === 0) {
                ul.innerHTML = '<li class="list-placeholder">⚠️ 目前暫無歷史錄影</li>';
                return;
            }
            data.recordings.forEach(filename => {
                const li = document.createElement('li');
                li.innerText = `🎬 ${filename}`;
                ul.appendChild(li);
            });
        })
        .catch(() => { ul.innerHTML = '<li class="list-placeholder">❌ 連線失敗</li>'; });
}

window.onload = function() {
    if (document.getElementById('cam-select')) loadRecordingsList();
};