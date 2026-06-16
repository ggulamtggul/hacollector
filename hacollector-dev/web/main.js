// Ingress Base Path 감지 함수
function getBasePath() {
    const path = window.location.pathname;
    if (path.includes('/api/hassio_ingress/')) {
        const idx = path.indexOf('/api/hassio_ingress/');
        // 'api/hassio_ingress/xxxxxxxx/' 구조의 슬래시까지 추출
        const endIdx = path.indexOf('/', idx + 20);
        if (endIdx !== -1) {
            return path.substring(0, endIdx + 1);
        }
    }
    return './'; // fallback to relative
}

const BASE_PATH = getBasePath();
console.log("Detected Ingress Base Path:", BASE_PATH);

// 상태 변수
let currentAircons = [];
let isSendingCommand = false;

// 초기 로드 및 타이머 실행
document.addEventListener("DOMContentLoaded", () => {
    refreshData();
    // 3초 주기로 상태 및 로그 갱신
    setInterval(refreshData, 3000);
});

// 데이터 갱신 통합 함수
async function refreshData() {
    try {
        await Promise.all([
            fetchStatus(),
            fetchLogs()
        ]);
    } catch (err) {
        console.error("Error refreshing data:", err);
    }
}

// 상태 API 패치
async function fetchStatus() {
    try {
        const res = await fetch(`${BASE_PATH}api/status`);
        if (!res.ok) throw new Error("Status API HTTP Error");
        const data = await res.json();
        
        if (data.status === 'success') {
            // 버전 업데이트
            document.getElementById("version-string").textContent = data.version;
            
            // 설정 정보 갱신
            document.getElementById("cfg-ip").textContent = data.config.lg_server_ip;
            document.getElementById("cfg-port").textContent = data.config.lg_server_port;
            document.getElementById("cfg-mqtt-ip").textContent = data.config.mqtt_server;
            document.getElementById("cfg-mqtt-port").textContent = data.config.mqtt_port;
            document.getElementById("cfg-temp-range").textContent = `${data.config.min_temp}°C - ${data.config.max_temp}°C`;
            document.getElementById("cfg-scan-interval").textContent = `${data.config.scan_interval}초`;
            
            // 실내기 그리드 업데이트
            renderAircons(data.aircons);
        }
    } catch (err) {
        console.error("fetchStatus error:", err);
    }
}

// 로그 API 패치
async function fetchLogs() {
    try {
        const res = await fetch(`${BASE_PATH}api/logs`);
        if (!res.ok) throw new Error("Logs API HTTP Error");
        const data = await res.json();
        
        if (data.status === 'success') {
            const consoleBox = document.getElementById("log-console");
            
            // 스크롤이 끝까지 내려가 있었는지 체크
            const isScrolledToBottom = consoleBox.scrollHeight - consoleBox.clientHeight <= consoleBox.scrollTop + 10;
            
            // 로그 내용 포맷팅
            if (data.logs.length === 0) {
                consoleBox.innerHTML = `<div class="text-zinc-600">// No logs recorded in memory yet.</div>`;
            } else {
                consoleBox.innerHTML = data.logs.map(log => {
                    // level에 따른 색상 하이라이트
                    let colorClass = "text-slate-300";
                    if (log.includes(" DEBUG:")) colorClass = "text-zinc-500";
                    if (log.includes("  INFO:")) colorClass = "text-emerald-400";
                    if (log.includes("  WARN:")) colorClass = "text-amber-400";
                    if (log.includes(" ERROR:") || log.includes("CRITICAL:")) colorClass = "text-rose-500 font-bold";
                    
                    return `<div class="${colorClass}">${escapeHtml(log)}</div>`;
                }).join('');
            }
            
            // 맨 아래로 자동 스크롤
            if (isScrolledToBottom) {
                consoleBox.scrollTop = consoleBox.scrollHeight;
            }
        }
    } catch (err) {
        console.error("fetchLogs error:", err);
    }
}

// 에어컨 카드 렌더링
function renderAircons(aircons) {
    const grid = document.getElementById("aircon-grid");
    document.getElementById("ac-count").textContent = `장치: ${aircons.length}대`;
    
    if (aircons.length === 0) {
        grid.innerHTML = `
            <div class="lg:col-span-2 py-12 flex flex-col items-center justify-center glass rounded-2xl text-slate-500">
                <p>발견된 실내기 장치가 없습니다. 설정을 확인해 주세요.</p>
            </div>`;
        return;
    }
    
    currentAircons = aircons;
    
    let html = "";
    aircons.forEach(ac => {
        const isOff = ac.action === 'off' || ac.action === '';
        const isOnline = ac.available === 'online' || ac.available === '';
        
        // 가용성 상태 스타일
        const availBadge = isOnline 
            ? `<span class="px-2 py-0.5 text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-semibold">Online</span>`
            : `<span class="px-2 py-0.5 text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded font-semibold">Offline</span>`;
            
        // 온/오프 토글 버튼 스타일
        const powerBtnClass = isOff 
            ? "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white" 
            : "bg-indigo-600 text-white hover:bg-indigo-500 font-bold shadow-lg shadow-indigo-600/30";

        // 모드 텍스트 한글화
        const modeKorean = {
            'cool': '냉방',
            'dry': '제습',
            'fan_only': '송풍',
            'auto': '인공지능',
            'heat': '난방'
        }[ac.opmode] || ac.opmode || '상태조회';

        // 풍량 텍스트 한글화
        const fanKorean = {
            'low': '약풍',
            'medium': '중풍',
            'high': '강풍',
            'auto': '자동',
            'silent': '절전',
            'power': '파워',
            'off': '정지'
        }[ac.fanmode] || ac.fanmode || '-';

        html += `
        <div class="glass rounded-2xl p-6 flex flex-col justify-between space-y-6 glass-card relative overflow-hidden transition-all duration-300">
            
            <!-- Card Header -->
            <div class="flex justify-between items-start">
                <div>
                    <div class="flex items-center gap-2 mb-1">
                        <h3 class="text-lg font-bold text-white">${escapeHtml(ac.room_name)}</h3>
                        ${availBadge}
                    </div>
                    <p class="text-xs text-slate-500">주소 ID: 0x${ac.id.toString(16).toUpperCase().padStart(2, '0')} (${ac.id})</p>
                </div>
                <!-- Power Toggle Button -->
                <button onclick="togglePower('${ac.room_name}')" class="p-3 rounded-xl transition-all ${powerBtnClass}" ${!isOnline ? 'disabled' : ''}>
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
                    </svg>
                </button>
            </div>

            <!-- Temperature display & controls -->
            <div class="flex items-center justify-between">
                <div class="space-y-1">
                    <span class="text-xs text-slate-500 font-medium uppercase tracking-wider block">실내 온도</span>
                    <span class="text-3xl font-extrabold tracking-tight text-transparent bg-gradient-to-r from-slate-100 to-slate-300 bg-clip-text">
                        ${ac.current_temp.toFixed(1)}°C
                    </span>
                </div>
                
                <!-- Temp Controls (Only available if AC is ON) -->
                <div class="flex items-center gap-3 bg-zinc-900/50 border border-white/5 rounded-xl p-1.5 ${isOff ? 'opacity-30 pointer-events-none' : ''}">
                    <button onclick="adjustTemp('${ac.room_name}', -1)" class="w-8 h-8 rounded-lg bg-zinc-800 text-slate-300 hover:text-white flex items-center justify-center font-bold text-lg hover:bg-white/5 transition-all">-</button>
                    <span class="w-10 text-center font-bold text-lg text-indigo-400">${ac.target_temp}°C</span>
                    <button onclick="adjustTemp('${ac.room_name}', 1)" class="w-8 h-8 rounded-lg bg-zinc-800 text-slate-300 hover:text-white flex items-center justify-center font-bold text-lg hover:bg-white/5 transition-all">+</button>
                </div>
            </div>

            <!-- Operational status info (Footer of Card) -->
            <div class="grid grid-cols-3 gap-2 text-center text-xs pt-4 border-t border-white/5">
                <div class="bg-white/5 p-2 rounded-xl border border-white/5">
                    <span class="text-slate-500 block text-[10px] mb-1">운전 상태</span>
                    <span class="font-bold ${isOff ? 'text-slate-500' : 'text-emerald-400'}">${isOff ? '꺼짐' : '켜짐'}</span>
                </div>
                <div class="bg-white/5 p-2 rounded-xl border border-white/5">
                    <span class="text-slate-500 block text-[10px] mb-1">운전 모드</span>
                    <span class="font-bold ${isOff ? 'text-slate-500' : 'text-cyan-400'}">${isOff ? '-' : modeKorean}</span>
                </div>
                <div class="bg-white/5 p-2 rounded-xl border border-white/5">
                    <span class="text-slate-500 block text-[10px] mb-1">바람 세기</span>
                    <span class="font-bold ${isOff ? 'text-slate-500' : 'text-amber-400'}">${isOff ? '-' : fanKorean}</span>
                </div>
            </div>
            
        </div>
        `;
    });
    
    grid.innerHTML = html;
}

// 전원 토글 액션
async function togglePower(roomName) {
    if (isSendingCommand) return;
    const ac = currentAircons.find(item => item.room_name === roomName);
    if (!ac) return;

    const nextAction = ac.action === 'off' ? 'on' : 'off';
    const body = {
        room_name: roomName,
        action: nextAction
    };

    // 만약 켜는 것이라면 디폴트 쿨모드 지정
    if (nextAction === 'on' && ac.opmode === '') {
        body.opmode = 'cool';
    }

    await sendControlCommand(body);
}

// 온도 조절 액션
async function adjustTemp(roomName, delta) {
    if (isSendingCommand) return;
    const ac = currentAircons.find(item => item.room_name === roomName);
    if (!ac || ac.action === 'off') return;

    const nextTemp = ac.target_temp + delta;
    await sendControlCommand({
        room_name: roomName,
        target_temp: nextTemp
    });
}

// REST API를 이용해 제어명령 전달
async function sendControlCommand(payload) {
    isSendingCommand = true;
    try {
        const res = await fetch(`${BASE_PATH}api/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Control API HTTP Error");
        const data = await res.json();
        
        if (data.status === 'success') {
            console.log("Command queued successfully:", payload);
            // 큐 전송 후 UI 빠른 갱신 반응성을 위해 300ms 후 상태 다시 읽기
            setTimeout(fetchStatus, 300);
        } else {
            alert("제어 실패: " + data.message);
        }
    } catch (err) {
        console.error("sendControlCommand Error:", err);
        alert("통신 에러가 발생했습니다.");
    } finally {
        isSendingCommand = false;
    }
}

// 보조 함수: HTML 이스케이프 (XSS 방어)
function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
