# Humicon SmartHome Add-ons for Home Assistant

이 레포지토리는 홈어시스턴트(Home Assistant)에서 휴미컨(Humicon) 통합 제어기 및 관련 기기들을 스마트하게 제어하기 위한 커스텀 애드온을 제공합니다.

## 제공되는 애드온 (Available Add-ons)

### [Humicon MQTT Daemon](./humicon_mqtt_daemon)
휴미컨 통합제어기와 Elfin EW11(RS485 to Wi-Fi)을 연동하여, 모드버스(Modbus) 패킷을 고속으로 가로채고(Sniffing) 스마트하게 폴링(Polling)하는 하이브리드 MQTT 데몬입니다.
휴미컨의 모든 센서 데이터(온습도, CO2, 미세먼지)와 제어 기능(목표 습도, 프리셋 모드, 켜짐/꺼짐)을 홈어시스턴트에 완벽하게 연동해 줍니다.

## 저장소 추가 방법 (How to add this repository)

1. Home Assistant 사이드바에서 **설정(Settings)** -> **애드온(Add-ons)** 으로 이동합니다.
2. 우측 하단의 **애드온 스토어(Add-on Store)** 버튼을 클릭합니다.
3. 우측 상단의 점 3개 메뉴(⋮)를 누르고 **저장소(Repositories)** 를 선택합니다.
4. 아래 주소를 복사하여 붙여넣고 **추가(Add)** 를 누릅니다.
   ```text
   https://github.com/nwhur/humicon-ha-addons
   ```
5. 스토어 목록을 새로고침하면 `Humicon MQTT Daemon` 애드온을 확인하고 설치할 수 있습니다!
