# Humicon MQTT Daemon 상세 설명서

## 개요
이 홈어시스턴트 애드온은 휴미컨(Humicon) 통합 제어기에서 발생하는 모드버스(Modbus) RS485 통신 패킷을 Wi-Fi(Elfin EW11)를 통해 실시간으로 스니핑 및 제어하는 하이브리드 MQTT 데몬입니다.

## 🛠 하드웨어 구성
1. 휴미컨 룸콘의 RS485 단자에 **Elfin EW11**을 연결합니다.
2. EW11 관리자 페이지에서 Protocol을 **None(Transparent)** 모드로 설정합니다.
3. TCP Server 포트(기본 8899)를 설정하여 홈어시스턴트에서 접근할 수 있도록 구성합니다.

## ⚙️ 설정 방법 (Configuration)
애드온의 `Configuration` 탭에서 다음 항목들을 반드시 설정해 주셔야 정상 작동합니다.

* `ew11_host`: EW11이 할당받은 로컬 IP 주소 (예: 192.168.1.100)
* `ew11_port`: EW11 TCP 포트 (기본값: 8899)
* `mqtt_host`: HA 내부 모스퀴토 브로커 주소 (기본값: core-mosquitto)
* `mqtt_port`: MQTT 포트 (기본값: 1883)
* `mqtt_user`: MQTT 사용자 이름 (HA 사용자 계정)
* `mqtt_password`: MQTT 비밀번호

## 🧩 제공되는 홈어시스턴트 엔티티
설정이 완료되고 데몬이 성공적으로 연결되면 MQTT Discovery를 통해 다음 엔티티들이 자동으로 등록됩니다.

### 기기 (Device)
* **Humicon Smart Cooler** (통합 기기로 등록됨)

### 통합 제어기 (Fan 엔티티)
* `fan.hyumikeon_tonghab_jeeogi`: 프리셋 모드(스마트, 환기, 청정, 제습 등) 및 풍량 제어, 켜짐/꺼짐 통합 지원

### 텍스트 센서 / 셀렉트 (Select / Sensor)
* `select.humicon_mogpyo_seubdo`: 목표 습도를 5% 단위나 프리셋(에코, 쾌적, 건조)으로 선택
* `sensor.humicon_jagdong_modeu`: 작동 모드의 히스토리 추적을 위한 전용 센서
* `switch.humicon_rc_lock`: 룸콘 물리 조작 잠금 기능 (On/Off)

### 센서 (Sensor)
* 실내 온도, 실내 습도, 외부 온도, 외부 습도
* 실내 CO2, 미세먼지(PM10), 초미세먼지(PM2.5)

## 🐛 트러블슈팅
* **연결 오류가 발생하는 경우:** 설정에서 `ew11_host`가 올바르게 입력되었는지 확인하고, EW11 웹 설정 페이지에서 동시에 접속된 다른 세션이 있는지 확인하십시오.
* **로그 확인:** 애드온의 `Log` 탭에서 `Connected to EW11 Raw Socket!` 및 `Connected to MQTT Broker!` 메시지가 보이는지 확인하십시오.
