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
- **Sniffing (Passive):** 룸콘 조작 시 실시간(Zero-delay) 반응성을 얻기 위해 두 가지 패킷을 모두 훔쳐봐야 합니다.
  1) 룸콘이 보내는 제어 명령(`0x06` 단일 쓰기, `0x10` 다중 쓰기) 프레임을 가로채어 즉시 MQTT 상태를 업데이트.
  2) 룸콘이 정기적으로 기기에 요청하고 응답받는 데이터(`0x03`, `0x04` 읽기 응답)를 가로채어 센서값을 업데이트.
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

### 4.1. 생성되어야 할 엔티티(Entity) 세부 설정 명세
다른 AI가 HA UI를 똑같이 렌더링하기 위해서는 아래의 엔티티 속성(options, icon 등)을 정확히 MQTT Discovery Payload에 포함해야 합니다.

| 종류 | Entity ID (예상) | 엔티티 이름 | 아이콘 (Icon) | 속성 및 제어 옵션 (Options) |
| :--- | :--- | :--- | :--- | :--- |
| **Fan** | `fan.humicon_unified_fan` | 휴미컨 통합 제어기 | 기본값 | `preset_modes`: `["꺼짐", "스마트", "제습 자동", "제습 수동", "환기 자동", "환기 수동", "바이패스", "청정 자동", "청정 수동"]`<br>`speed_range_min`: 1, `speed_range_max`: 3 |
| **Select** | `select.humicon_target_humidity` | 휴미컨 목표 습도 | `mdi:water-percent` | `options`: `["에코", "쾌적", "건조", "30%", "35%", "40%", "45%", "50%", "55%", "60%"]` (정확히 5% 단위) |
| **Select** | `select.humicon_fan_speed` | 휴미컨 풍량 | `mdi:fan` | `options`: `["꺼짐", "자동", "약풍", "중풍", "강풍"]` |
| **Sensor** | `sensor.humicon_operation_mode` | 휴미컨 작동 모드 | `mdi:refresh-auto` | 현재 모드 텍스트 출력 |
| **Sensor** | `sensor.humicon_indoor_temp` | 휴미컨 실내 온도 | 기본값 | `device_class: temperature`, `unit_of_measurement: °C` |
| **Sensor** | `sensor.humicon_indoor_humidity`| 휴미컨 실내 습도 | 기본값 | `device_class: humidity`, `unit_of_measurement: %` |
| **Sensor** | `sensor.humicon_co2` | 휴미컨 실내 CO2 | 기본값 | `device_class: carbon_dioxide`, `unit_of_measurement: ppm` |
| **Sensor** | `sensor.humicon_pm10` | 휴미컨 실내 미세먼지 | 기본값 | `device_class: pm10`, `unit_of_measurement: µg/m³` |
| **Sensor** | `sensor.humicon_pm25` | 휴미컨 초미세먼지 | 기본값 | `device_class: pm25`, `unit_of_measurement: µg/m³` |
| **Switch** | `switch.humicon_rc_lock` | 휴미컨 RC 잠금 | 기본값 | `payload_on`: "ON", `payload_off`: "OFF" |

### 4.2. High Availability 및 상태 토픽 매핑
- **Command Topic:** `humicon/cmd/[기능명]` (예: power, mode, fan, target_humidity, rc_lock 등)
- **State Topic:** `humicon/state/[기능명]`
- 모든 엔티티의 **Availability Topic:** `humicon/state/availability` (연결 시 `online`, 끊김 시 `offline` 발행)
- **상태 중복 제거(State Caching):** 파이썬 메모리 딕셔너리(`last_state`)에 마지막으로 발행한 상태값을 저장해두고, **실제 상태가 변경되었을 때만 MQTT에 발행**해야 합니다. (이벤트 버스 스팸 방지)
- **Retain 플래그 필수:** 모든 `State Topic`과 `Availability Topic`을 발행할 때는 반드시 **`retain=True`** 플래그를 설정하여, HA가 재시작되어도 이전 상태를 즉각 복구할 수 있도록 해야 합니다.
- 이를 통해 네트워크 단절 시 HA 대시보드에서 기기가 "사용 불가" 처리되어 오작동을 방지해야 합니다.

---

## 5. Add-on 패키징 및 설정 (Configuration)
HA Supervisor 호환 애드온으로 구동하기 위한 명세입니다.

### 5.1. `config.yaml` 및 환경 설정 주입 로직
- 사용자는 UI에서 설정값을 입력하며, 데몬 코드(`humicon_daemon.py`)는 HA Supervisor가 제공하는 **`/data/options.json`** 파일을 직접 파싱하여 설정값을 불러와야 합니다.
- **필수 속성:** `ew11_host`, `ew11_port`, `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password`, `language` (ko/en)

### 5.2. 예외 처리 및 방어 로직 (Fail-safe)
* **스레드 세이프(Thread-Safe) 소켓:** Sniffing 쓰레드와 Polling 쓰레드가 동일한 TCP 소켓을 공유하므로, 반드시 **Mutex(Lock)**를 사용하여 패킷 충돌을 막아야 합니다.
* **Write 직후 Polling 유예 (충돌 방지):** RS485 특성상 제어 명령(Write)을 보낸 직후에는 메인보드가 처리할 시간을 주어야 합니다. 제어 명령 전송 후 **최소 2초 동안은 Active Polling을 중단(Backoff)**해야만 패킷 깨짐을 방지할 수 있습니다.
* **TCP Reconnect:** EW11 연결이 실패하거나 예기치 않게 끊어지면, 5~10초 간격으로 무한히 재연결을 시도해야 합니다.
* **버퍼 쓰레기값 필터링:** TCP 소켓 특성상 여러 패킷이 붙어서 오거나 잘려서 올 수 있으므로, 반드시 바이트 버퍼를 쌓아두고 시작점과 CRC-16을 완벽히 검증한 후 파싱해야 합니다.

---

## 6. 다국어 지원 명세 (i18n)
언어 설정(`language` 옵션)에 따라 HA에 등록되는 **엔티티 이름, 모드 이름, 상태 텍스트**가 동적으로 번역되어야 합니다. 단, 고유 식별자(`unique_id`)와 MQTT 토픽은 언어 변경 시 HA 엔티티가 꼬이지 않도록 영문 고정이어야 합니다.

**양방향(Bidirectional) 번역 필수:**
HA UI에 번역된 텍스트(`Smart`, `Dehumidify Auto` 등)를 뿌려주면, 사용자가 그 버튼을 눌렀을 때 HA는 데몬에게 **번역된 영문 텍스트 그대로(`Smart`)** 명령을 보냅니다. 따라서 데몬의 `on_message` 로직은 들어온 영문 페이로드를 다시 원래의 **한국어 키값(`스마트`)으로 역번역(Reverse Translate)** 한 뒤에 파싱 로직을 수행해야 합니다.

**필수 번역 매핑 테이블:**
* 스마트 ➔ `Smart`
* 제습 자동 / 제습 수동 ➔ `Dehumidify Auto` / `Dehumidify Manual`
* 환기 자동 / 환기 수동 ➔ `Ventilate Auto` / `Ventilate Manual`
* 바이패스 ➔ `Bypass`
* 청정 자동 / 청정 수동 ➔ `Purify Auto` / `Purify Manual`
* 꺼짐 / 자동 / 약풍 / 중풍 / 강풍 ➔ `Off` / `Auto` / `Low` / `Medium` / `High`
* 에코 / 쾌적 / 건조 ➔ `Eco` / `Comfort` / `Dry`
