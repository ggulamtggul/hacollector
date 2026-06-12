# HA Collector (LG System Aircon Edition) v2.0

**Home Assistant Add-on for LG System Aircon (RS485)**  
이 애드온은 RS485 to Ethernet 게이트웨이(예: EW11)를 통해 LG 시스템 에어컨을 Home Assistant의 MQTT와 연동해주는 도구입니다.

Current Version: **v2.0.0**

## ✨ v2.0 주요 특징 및 개선사항
* **자동 검색 (Auto Discovery)**: RS485 주소를 스캔하여 에어컨 장치를 찾고 자동으로 등록하는 기능 탑재. Double-Check 검증 알고리즘이 내장되어 유령 기기(Ghost Devices) 등록을 방지합니다.
* **RS485 통신 안정성 극대화**: 
  * TCP Keep-Alive 최적화
  * 소켓 버퍼 오염 방지 및 자동 복구 메커니즘
  * 기기 연결 후 안정화 딜레이(0.3s) 적용
* **최신 HAOS 표준 준수**: Python 3.13-alpine 기반의 공식 멀티 아키텍처(aarch64, amd64) 베이스 이미지를 활용하여 s6-overlay 등 HAOS 생태계에 완벽히 호환됩니다.
* **Paho MQTT v2 호환**: 최신 MQTT 프로토콜 통신 스펙에 완벽 대응합니다.

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
| `auto_scan` | 기기 자동 검색 사용 여부 | `true` |
| `auto_scan_range` | 자동 검색 최대 범위 | `16` |
| `rooms` | 수동 매핑 시 에어컨 ID와 방 이름 매핑 리스트 | `[]` |
| `min_temp` | 설정 가능한 최소 온도 | `18` |
| `max_temp` | 설정 가능한 최대 온도 | `30` |
| `scan_interval` | 상태 갱신 주기 (초) | `20` |
| `log_level` | 로그 레벨 (info, debug) | `info` |

### 자동 검색 기능 작동 방식
`auto_scan`이 `true`로 설정되어 있으면 부팅 시 설정된 범위(`auto_scan_range`) 내에서 RS485 기기를 전수 조사합니다.
검색된 기기들은 `auto_room_0x0A` 와 같은 임시 이름으로 HA에 등록되며, 이후 MQTT에서 바로 확인 가능합니다.
사용자가 이미 `rooms`에 수동으로 기기를 매핑했다면, 자동 검색 기능은 설정되지 않은 기기들만 검색 후 등록합니다.

## 🚀 설치 방법
1. **Repository 추가**: Home Assistant 애드온 스토어 > 우측 상단 메뉴 > "저장소 관리" > URL 입력
   ```
   https://github.com/ggulamtggul/hacollector
   ```
2. **설치**: "HA Collector" 애드온 선택 후 설치
3. **설정**: 설정 탭에서 IP 및 기타 정보 입력
4. **시작**: 애드온 시작 (로그 확인)

상세 변경 내역은 [CHANGELOG.md](./CHANGELOG.md)를 참조하세요.
