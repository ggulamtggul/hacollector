# HACollector (LG System Aircon Edition)

hacollector는 Home Assistant에서 RS485 프로토콜을 사용하는 **LG 시스템 에어컨**을 제어하기 위한 Add-on입니다.

## 기능
* **LG 시스템 에어컨**
  * 온도 조절
  * 운전 모드 (냉방, 제습, 송풍, 난방, 자동)
  * 풍량 조절
  * 스윙(날개) 제어
  * 전원 제어

## 요구사항
* **하드웨어**: EW11 (RS485 to Ethernet) 등의 게이트웨이 장비
* **소프트웨어**: Home Assistant OS (MQTT Broker 필수)

## 설치 방법 (Home Assistant 로컬 애드온)
1. Home Assistant의 `/addons` 폴더에 `hacollector` 폴더를 생성합니다.
2. 이 저장소의 파일들을 해당 폴더에 복사합니다.
3. Home Assistant > 설정 > 애드온 > 애드온 스토어 > "업데이트 확인"
4. "HA Collector" 설치 및 설정(MQTT, LG 서버 IP 등) 입력 후 실행

## Changelog
* **0.90**: MQTT Availability(LWT) 추가로 연결 끊김 감지 강화, 코드 리팩토링.
