# Humicon HA Connector 시스템 요구사항 명세서 (PRD / SRS)

본 문서는 **휴미컨(Humicon) 통합 제어기**를 홈어시스턴트(Home Assistant)에 연동하기 위한 'Humicon HA Connector' 애드온의 기능, 아키텍처, UI 및 통신 프로토콜을 정의한 요구사항 명세서입니다. 다른 AI나 개발자가 이 문서를 기반으로 동일한 시스템을 완벽하게 재구현(Reverse Engineering)할 수 있도록 상세히 기술되었습니다.

---

## 1. 개요 (Overview)
- **프로젝트 명:** Humicon HA Connector (이전 명칭: Humicon MQTT Daemon)
- **목적:** 휴미컨의 자체 컨트롤러(룸콘)와 메인 장비 간의 RS485 통신을 가로채고(Sniffing) 제어 명령을 주입(Polling/Writing)하여, 홈어시스턴트에서 모든 기능을 원격으로 확인하고 제어할 수 있도록 함.
- **주요 기술 스택:** Python 3.11+, Paho-MQTT, Home Assistant Add-on(Docker / bashio), HA MQTT Discovery

---

## 2. 하드웨어 및 네트워크 아키텍처 (Architecture)
### 2.1. 하드웨어 구성
- **대상 기기:** 휴미컨(Humicon) 통합 제어 시스템
- **통신 인터페이스:** Elfin EW11 (RS485 to Wi-Fi 변환기)
  - 룸콘의 RS485 A/B 단자에 브릿지 연결.

### 2.2. EW11 통신 설정 요구사항
- **통신 모드:** Transparent Mode (단순 TCP 소켓 통신)
- **프로토콜:** TCP Server 모드 (기본 포트: 8899)
- **RS485 세팅:** Baudrate 9600, Data bits 8, Stop bits 1, Parity None

### 2.3. 하이브리드 통신 로직 (핵심)
이 데몬은 단순한 1:1 통신이 아닙니다. 기존 룸콘이 마스터(Master) 역할을 하므로, 충돌 방지를 위해 **Sniffing + Active Polling 하이브리드 구조**를 가져야 합니다.
- **Sniffing (Passive):** 룸콘이 지속적으로 보내는 폴링 요청(`01 03 00 00...`)에 대한 기기의 응답을 훔쳐보고(Sniffing) 즉시 MQTT로 발행합니다. 이로 인해 물리적 조작 시 지연 없는(Real-time) 반응성을 확보합니다.
- **Polling (Active):** 기동 시 룸콘이 켜져있지 않거나, 특정 잉여 데이터가 필요할 때만 0.5초 대기 후 안전하게 폴링 명령을 주입합니다.

---

## 3. Modbus (RS485) 프로토콜 명세
모든 통신은 Hexadecimal(16진수) 바이트 배열 기반이며, CRC-16(Modbus) 체크섬을 포함합니다.

### 3.1. 상태 조회 (Read)
데몬은 주기적으로 두 가지 영역을 폴링합니다. (Holding Register `0x03` 및 Input Register `0x04`)

#### A. Input Registers (명령어: `0x04`, 주소 0번부터 22개 읽기)
- **요청 (TX):** `01 04 00 00 00 16 [CRC]`
- **데이터 파싱 주소 매핑 (2바이트씩):**
  - **[Address 3]** 전원 상태 (1: ON, 0: OFF)
  - **[Address 4]** 작동 모드 (1: 스마트, 2: 제습 자동, 3: 제습 수동, 4: 환기 자동, 5: 환기 수동, 6: 바이패스, 7: 청정 자동, 8: 청정 수동)
  - **[Address 6]** 목표 습도 모드 (0: 에코, 1: 쾌적, 2: 건조, 3: 사용자 지정)
  - **[Address 7]** 목표 습도 수치 (예: 45 -> 45%)
  - **[Address 8]** 풍량 (0: 꺼짐, 1: 약풍, 2: 중풍, 3: 강풍, 4: 자동)
  - **[Address 13]** 실내 온도 (int16 파싱 필요, 실제값)
  - **[Address 14]** 실내 습도
  - **[Address 16]** 실내 CO2
  - **[Address 17]** 실내 PM10
  - **[Address 18]** 실내 PM2.5
  - **[Address 20]** 외부 온도 (int16 파싱)
  - **[Address 21]** 외부 습도

#### B. Holding Registers (명령어: `0x03`, 주소 0번부터 6개 읽기)
- **요청 (TX):** `01 03 00 00 00 06 [CRC]`
- **데이터 파싱 주소 매핑:**
  - **[Address 0]** RC 잠금 상태 (1: ON, 0: OFF)

### 3.2. 제어 명령 주입 (Write)
명령을 보낼 때는 단일 레지스터 쓰기(`0x06`) 함수를 사용합니다.
- **[Address 1] 전원:** `01 06 00 01 00 01 [CRC]` (켜기) / `01 06 00 01 00 00 [CRC]` (끄기)
- **[Address 2] 작동 모드:** `01 06 00 02 00 04 [CRC]` (환기 자동 등, 위의 모드 번호 매핑 사용)
- **[Address 3] 습도 모드:** `01 06 00 03 00 00 [CRC]` (에코) 등
- **[Address 4] 습도 수치:** `01 06 00 04 00 2D [CRC]` (45%)
- **[Address 5] 풍량:** `01 06 00 05 00 01 [CRC]` (약풍)
- **[Address 14] RC 잠금:** `01 06 00 0E 00 01 [CRC]` (잠금 켜기)

### 3.3. CRC-16 계산 알고리즘 명세
Python 구현 시 다음 알고리즘을 준수해야 합니다.
- **Polynomial:** `0xA001`
- **초기값:** `0xFFFF`
- 결과값은 Little Endian 형식으로 패킹하여 프레임 끝에 부착해야 합니다.

---

## 4. 홈어시스턴트(HA) 연동 명세 (MQTT Discovery)
데몬은 시작 시 `homeassistant/#` 토픽을 통해 기기를 자동 등록(Auto-Discovery)해야 합니다.

### 4.1. 생성되어야 할 엔티티(Entity) 목록
| 종류 | Entity ID (예상) | 이름 (번역 지원) | 역할 |
| :--- | :--- | :--- | :--- |
| **Fan** | `fan.humicon_unified_fan` | 휴미컨 통합 제어기 | 전원 On/Off, preset_mode(스마트, 제습 등), percentage(1~3: 약/중/강풍, 4: 자동) 제어 |
| **Select** | `select.humicon_target_humidity` | 휴미컨 목표 습도 | 습도 30~60% 및 에코/쾌적/건조 프리셋 선택 |
| **Sensor** | `sensor.humicon_operation_mode` | 휴미컨 작동 모드 | 현재 어떤 모드로 구동 중인지 텍스트 표시 |
| **Sensor** | `sensor.humicon_indoor_temp` | 휴미컨 실내 온도 | 온도 (°C) - `device_class: temperature` |
| **Sensor** | `sensor.humicon_indoor_humidity`| 휴미컨 실내 습도 | 습도 (%) - `device_class: humidity` |
| **Sensor** | `sensor.humicon_co2` | 휴미컨 실내 CO2 | 이산화탄소 농도 (ppm) |
| **Sensor** | `sensor.humicon_pm10` | 휴미컨 실내 미세먼지 | 미세먼지 (µg/m³) |
| **Sensor** | `sensor.humicon_pm25` | 휴미컨 초미세먼지 | 초미세먼지 (µg/m³) |
| **Switch** | `switch.humicon_rc_lock` | 휴미컨 RC 잠금 | 룸콘 물리 버튼 조작 잠금 기능 |

### 4.2. High Availability (가용성 관리)
- 모든 엔티티는 `availability_topic` (`humicon/status`)을 가져야 합니다.
- 데몬이 EW11과 연결되면 `online`을 발행하고, 연결이 끊기면 즉각 `offline`을 발행해야 합니다.
- 이를 통해 네트워크 단절 시 HA 대시보드에서 기기가 "사용 불가" 처리되어 오작동을 방지해야 합니다.

---

## 5. Add-on 패키징 및 설정 (Configuration)
HA Supervisor 호환 애드온으로 구동하기 위한 명세입니다.

### 5.1. `config.yaml` 요구사항
사용자는 다음 정보를 UI에서 입력할 수 있어야 합니다.
* `ew11_host` (필수): EW11의 IP 주소 (문자열)
* `ew11_port` (필수): EW11 포트 (정수, 기본 8899)
* `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` (필수)
* **`language` (필수):** `ko` (한국어) 또는 `en` (영어) 선택 기능 (i18n 지원용)

### 5.2. 예외 처리 및 방어 로직 (Fail-safe)
* **IP 미입력 에러 방지:** `ew11_host`가 비어있을 경우 무한 연결 시도로 인한 로그 도배를 막기 위해 에러 메시지를 출력하고 무한 대기(Sleep) 상태로 전환해야 합니다.
* **TCP Reconnect:** EW11 연결이 실패하거나 예기치 않게 끊어지면, 5~10초 간격으로 무한히 재연결을 시도해야 합니다.
* **버퍼 쓰레기값 필터링:** TCP 소켓 특성상 여러 패킷이 붙어서 오거나 잘려서 올 수 있으므로, 반드시 바이트 버퍼를 쌓아두고 `0x01` 시작점과 CRC-16을 완벽히 검증한 후 파싱해야 합니다.

---

## 6. 다국어 지원 명세 (i18n)
언어 설정(`language` 옵션)에 따라 HA에 등록되는 **엔티티 이름, 모드 이름, 상태 텍스트**가 동적으로 번역되어야 합니다. 단, 고유 식별자(`unique_id`)와 MQTT 토픽은 언어 변경 시 HA 엔티티가 꼬이지 않도록 영문 고정이어야 합니다.

**필수 번역 매핑 테이블:**
* 스마트 ➔ `Smart`
* 제습 자동 / 제습 수동 ➔ `Dehumidify Auto` / `Dehumidify Manual`
* 환기 자동 / 환기 수동 ➔ `Ventilate Auto` / `Ventilate Manual`
* 바이패스 ➔ `Bypass`
* 청정 자동 / 청정 수동 ➔ `Purify Auto` / `Purify Manual`
* 꺼짐 / 자동 / 약풍 / 중풍 / 강풍 ➔ `Off` / `Auto` / `Low` / `Medium` / `High`
* 에코 / 쾌적 / 건조 ➔ `Eco` / `Comfort` / `Dry`
