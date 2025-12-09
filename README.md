# HA Collector (LG System Aircon Edition)

**Home Assistant Add-on for LG System Aircon (RS485)**  
이 애드온은 RS485 to Ethernet 게이트웨이(예: EW11)를 통해 LG 시스템 에어컨을 Home Assistant의 MQTT와 연동해주는 도구입니다.

Current Version: **v1.0.0**

## ✨ 주요 기능
* **완벽한 제어**: 온도, 운전 모드(냉방/난방/제습/송풍/자동), 풍량, 스윙, 전원 제어
* **Home Assistant Auto Discovery**: 설정된 에어컨(Climate) 장치를 HA에 자동으로 등록합니다.
* **고성능 아키텍처**:
  * **Asyncio Queue**: 비동기 큐 기반의 효율적인 명령 처리로 CPU 사용량 최소화
  * **Persistent Connection**: RS485 게이트웨이와 지속적인 연결 유지로 빠른 반응 속도
* **사용 편의성**:
  * Home Assistant 애드온 설정(UI)에서 바로 옵션 변경 가능 (`options.json` 지원)
  * 에어컨 별명(Friendly Name) 지원 (공백 포함 가능)
  * 자동 검색(Auto Scan) 기능 내장

## 📋 요구 사항
* **하드웨어**: RS485 to Ethernet 변환기 (예: Elfin-EW11)
  * LG 실외기/실내기 RS485 단자에 연결되어 있어야 함 (채널 설정 확인)
* **소프트웨어**: Home Assistant (MQTT Broker 필수)

## ⚙️ 설정 (Configuration)
애드온 설치 후 **설정(Configuration)** 탭에서 다음 항목들을 직접 편집할 수 있습니다.

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `lg_server_ip` | RS485 게이트웨이 IP 주소 | `192.168.0.100` |
| `lg_server_port` | RS485 게이트웨이 포트 | `8899` |
| `mqtt_server` | MQTT 브로커 주소 (보통 core-mosquitto) | `core-mosquitto` |
| `mqtt_username` | MQTT 사용자 ID (선택) | |
| `mqtt_password` | MQTT 비밀번호 (선택) | |
| `rooms` | 에어컨 ID와 방 이름 매핑 리스트 | `[{"name": "livingroom", "id": 0}]` |
| `min_temp` | 설정 가능한 최소 온도 | `18` |
| `max_temp` | 설정 가능한 최대 온도 | `30` |
| `scan_interval` | 상태 갱신 주기 (초) | `20` |
| `log_level` | 로그 레벨 (info, debug) | `info` |

### Rooms 설정 예시
```yaml
rooms:
  - name: 거실
    id: 0
  - name: 침실
    id: 1
```
* **ID(id)**: 16진수 실내기 주소를 10진수로 입력 (예: 0x01 -> 1, 0x0A -> 10)
* **Name(name)**: Home Assistant에 표시될 이름 (한글, 공백 가능)

## 🚀 설치 방법
1. **Repository 추가**: Home Assistant 애드온 스토어 > 우측 상단 메뉴 > "저장소 관리" > URL 입력
   ```
   https://github.com/ggulamtggul/hacollector
   ```
2. **설치**: "HA Collector" 애드온 선택 후 설치
3. **설정**: 설정 탭에서 IP 및 방 정보 입력
4. **시작**: 애드온 시작 (로그 확인)

## 📝 Change Log
### v1.0.0 (Major Release)
* **Architecture**: Python `Asyncio Queue` 도입으로 성능 및 응답성 대폭 향상
* **Network**: Persistent Connection(지속 연결) 적용으로 불필요한 재연결 로그 제거
* **Config**: Home Assistant 애드온 설정 UI 완벽 지원 (`/data/options.json`)
* **Feature**: `scan_interval`, `min/max_temp` 설정 옵션 추가
* **Stabilization**: 초기 구동 시 블로킹 문제 해결, 소켓 재연결 로직 최적화

상세 변경 내역은 [CHANGELOG.md](./CHANGELOG.md)를 참조하세요.
