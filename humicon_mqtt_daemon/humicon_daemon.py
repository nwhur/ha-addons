import socket
import struct
import time
import json
import logging
import threading
import paho.mqtt.client as mqtt
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

OPTIONS_FILE = "/data/options.json"
options = {}
if os.path.exists(OPTIONS_FILE):
    try:
        with open(OPTIONS_FILE, "r") as f:
            options = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read options.json: {e}")

# MQTT & EW11 Configuration from options.json
MQTT_BROKER = options.get("mqtt_host", "core-mosquitto")
MQTT_PORT = options.get("mqtt_port", 1883)
MQTT_USER = options.get("mqtt_user", "mqtt")
MQTT_PASS = options.get("mqtt_password", "")

EW11_IP = options.get("ew11_host", "")
EW11_PORT = options.get("ew11_port", 8899)

if not EW11_IP:
    logging.error("CRITICAL: ew11_host is not configured! Please configure the Add-on in Home Assistant.")
    import sys
    sys.exit(1)

MODE_MAP = {
    1: "스마트", 2: "제습 자동", 3: "제습 수동",
    4: "환기 자동", 5: "환기 수동", 6: "환기 수동(bypass)",
    7: "청정 자동", 8: "청정 수동"
}
REV_MODE_MAP = {v: k for k, v in MODE_MAP.items()}

last_state = {}
socket_lock = threading.Lock()
sock = None

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def connect_ew11(mqtt_client):
    global sock
    while True:
        try:
            logging.info(f"Connecting to EW11 at {EW11_IP}:{EW11_PORT}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((EW11_IP, EW11_PORT))
            s.settimeout(None) # Blocking mode for sniffing
            with socket_lock:
                sock = s
            logging.info("Connected to EW11 Raw Socket!")
            if mqtt_client:
                mqtt_client.publish("humicon/state/availability", "online", retain=True)
            return
        except Exception as e:
            logging.error(f"EW11 connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

last_write_time = 0

def send_modbus_write(address: int, value: int):
    global sock, last_write_time
    frame = struct.pack(">BBHH", 1, 6, address, value)
    crc = crc16(frame)
    frame += struct.pack("<H", crc)
    
    with socket_lock:
        if sock:
            try:
                sock.sendall(frame)
                last_write_time = time.time()
                logging.info(f"Sent Write: Addr {address}, Val {value} | {frame.hex()}")
                time.sleep(0.3) # Prevent RS485 back-to-back write collision
            except Exception as e:
                logging.error(f"Failed to send modbus write: {e}")



def parse_int16(val: int) -> int:
    return val if val <= 32767 else val - 65536

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("Connected to MQTT Broker!")
        client.subscribe("humicon/cmd/#")
        setup_discovery(client)
    else:
        logging.error(f"Failed to connect, return code {reason_code}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload
        
        if topic == "humicon/cmd/power":
            val = 1 if payload == b"ON" else 0
            send_modbus_write(1, val)
            client.publish("humicon/state/power", "ON" if val == 1 else "OFF", retain=True)
            last_state["power"] = val
            
        elif topic == "humicon/cmd/mode":
            mode = payload.decode('utf-8') if isinstance(payload, bytes) else payload
            if mode == "꺼짐":
                send_modbus_write(1, 0)
                client.publish("humicon/state/power", "OFF", retain=True)
                last_state["power"] = "OFF"
            else:
                send_modbus_write(1, 1) # Ensure power is ON when selecting a mode
                time.sleep(0.3)
                for k, v in MODE_MAP.items():
                    if v == mode:
                        send_modbus_write(2, k)
                        break
                client.publish("humicon/state/power", "ON", retain=True)
                last_state["power"] = "ON"
            client.publish("humicon/state/mode", mode, retain=True)
            last_state["mode"] = mode
            
        elif topic == "humicon/cmd/fan":
            pct = int(float(payload))
            if pct == 0: val = 0
            elif pct == 1: val = 1
            elif pct == 2: val = 2
            elif pct == 3: val = 3
            elif pct <= 35: val = 1
            elif pct <= 70: val = 2
            else: val = 3
            send_modbus_write(5, val)
            if val == 1: pct_str = "1"
            elif val == 2: pct_str = "2"
            elif val == 3: pct_str = "3"
            else: pct_str = "0"
            client.publish("humicon/state/fan_percentage", pct_str, retain=True)
            last_state["fan_percentage"] = pct_str
        
        elif topic == "humicon/cmd/fan_speed":
            text = payload.decode('utf-8') if isinstance(payload, bytes) else payload
            if text == "꺼짐": val = 0
            elif text == "자동": val = 4
            elif text == "약풍": val = 1
            elif text == "중풍": val = 2
            elif text == "강풍": val = 3
            else: val = 1
            send_modbus_write(5, val)
            client.publish("humicon/state/fan_speed_text", text, retain=True)
            last_state["fan_speed_text"] = text
            
        elif topic == "humicon/cmd/target_humidity":
            payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else payload
            if payload_str == "에코":
                send_modbus_write(3, 0)
            elif payload_str == "쾌적":
                send_modbus_write(3, 1)
            elif payload_str == "건조":
                send_modbus_write(3, 2)
            else:
                pct = int(payload_str.replace('%', ''))
                send_modbus_write(3, 3) # Set mode to Custom
                time.sleep(0.3)
                send_modbus_write(4, pct) # Set custom percentage
            client.publish("humicon/state/target_humidity", payload_str, retain=True)
            last_state["target_humidity"] = payload_str
            
        elif topic == "humicon/cmd/rc_lock":
            val = 1 if payload == b"ON" else 0
            send_modbus_write(14, val)
            client.publish("humicon/state/rc_lock", "ON" if val == 1 else "OFF", retain=True)
            last_state["rc_lock"] = val
    except Exception as e:
        import traceback
        logging.error(f"Error handling message {msg.topic}: {msg.payload}")
        logging.error(traceback.format_exc())

def setup_discovery(client):
    device_info = {
        "identifiers": ["humicon_main"],
        "name": "Humicon",
        "manufacturer": "Humicon",
        "model": "Smart Cooler",
    }
    
    fan_config = {
        "name": "휴미컨 통합 제어기",
        "unique_id": "humicon_unified_fan_mqtt",
        "command_topic": "humicon/cmd/power",
        "state_topic": "humicon/state/power",
        "preset_mode_command_topic": "humicon/cmd/mode",
        "preset_mode_state_topic": "humicon/state/mode",
        "preset_modes": ["꺼짐"] + list(MODE_MAP.values()),
        "percentage_command_topic": "humicon/cmd/fan",
        "percentage_state_topic": "humicon/state/fan_percentage",
        "speed_range_min": 1,
        "speed_range_max": 3,
        "availability_topic": "humicon/state/availability",
        "device": device_info
    }
    client.publish("homeassistant/fan/humicon/unified_fan/config", json.dumps(fan_config), retain=True)

    sensors = [
        ("ra_temp", "휴미컨 실내 온도", "temperature", "°C"),
        ("ra_humidity", "휴미컨 실내 습도", "humidity", "%"),
        ("oa_temp", "휴미컨 외부 온도", "temperature", "°C"),
        ("oa_humidity", "휴미컨 외부 습도", "humidity", "%"),
        ("co2", "휴미컨 실내 CO2", "carbon_dioxide", "ppm"),
        ("pm10", "휴미컨 실내 미세먼지(PM10)", "pm10", "µg/m³"),
        ("pm25", "휴미컨 실내 초미세먼지(PM2.5)", "pm25", "µg/m³"),
    ]
    for sid, name, dev_cls, unit in sensors:
        conf = {
            "name": name,
            "unique_id": f"humicon_{sid}_mqtt",
            "state_topic": f"humicon/state/{sid}",
            "availability_topic": "humicon/state/availability",
            "device": device_info
        }
        if dev_cls: conf["device_class"] = dev_cls
        if unit: conf["unit_of_measurement"] = unit
        client.publish(f"homeassistant/sensor/humicon/{sid}/config", json.dumps(conf), retain=True)

    mode_sensor_conf = {
        "name": "휴미컨 작동 모드",
        "unique_id": "humicon_mode_sensor_mqtt",
        "state_topic": "humicon/state/mode",
        "icon": "mdi:refresh-auto",
        "availability_topic": "humicon/state/availability",
        "device": device_info
    }
    client.publish("homeassistant/sensor/humicon/mode/config", json.dumps(mode_sensor_conf), retain=True)

    rc_lock_conf = {
        "name": "휴미컨 RC 잠금",
        "unique_id": "humicon_rc_lock_mqtt",
        "command_topic": "humicon/cmd/rc_lock",
        "state_topic": "humicon/state/rc_lock",
        "availability_topic": "humicon/state/availability",
        "device": device_info
    }
    client.publish("homeassistant/switch/humicon/rc_lock/config", json.dumps(rc_lock_conf), retain=True)

    # Target Humidity
    target_hum_conf = {
        "name": "휴미컨 목표 습도",
        "unique_id": "humicon_target_humidity_mqtt",
        "command_topic": "humicon/cmd/target_humidity",
        "state_topic": "humicon/state/target_humidity",
        "options": ["에코", "쾌적", "건조"] + [f"{i}%" for i in range(30, 65, 5)],
        "icon": "mdi:water-percent",
        "availability_topic": "humicon/state/availability",
        "device": device_info
    }
    client.publish("homeassistant/select/humicon/target_humidity/config", json.dumps(target_hum_conf), retain=True)

    fan_speed_conf = {
        "name": "휴미컨 풍량",
        "unique_id": "humicon_fan_speed_mqtt",
        "command_topic": "humicon/cmd/fan_speed",
        "state_topic": "humicon/state/fan_speed_text",
        "options": ["꺼짐", "자동", "약풍", "중풍", "강풍"],
        "icon": "mdi:fan",
        "availability_topic": "humicon/state/availability",
        "device": device_info
    }
    client.publish("homeassistant/select/humicon/fan_speed/config", json.dumps(fan_speed_conf), retain=True)

    # Clear the old number entity if it exists
    client.publish("homeassistant/number/humicon/target_humidity/config", "", retain=True)

last_start_addr_03 = -1
last_start_addr_04 = -1

def process_frame_03(client, start_addr, byte_count, data_bytes):
    if byte_count % 2 != 0: return
    regs = struct.unpack(f'>{byte_count//2}H', data_bytes)
    
    reg_map = {}
    for idx, val in enumerate(regs):
        reg_map[start_addr + idx] = val
        
    current_state = {}
    # RC Lock (Address 0)
    if 0 in reg_map:
        current_state["rc_lock"] = "ON" if reg_map[0] == 1 else "OFF"
        
    for k, v in current_state.items():
        if last_state.get(k) != v:
            client.publish(f"humicon/state/{k}", str(v), retain=True)
            last_state[k] = v

def process_frame_04(client, start_addr, byte_count, data_bytes):
    if byte_count % 2 != 0: return
    regs = struct.unpack(f'>{byte_count//2}H', data_bytes)
    
    reg_map = {}
    for idx, val in enumerate(regs):
        reg_map[start_addr + idx] = val
        
    current_state = {}
    
    # Power, Mode, Fan Speed from 0x04 Input Registers
    if 3 in reg_map:
        is_on = (reg_map[3] == 1)
        current_state["power"] = "ON" if is_on else "OFF"
    
    if 4 in reg_map:
        if current_state.get("power", last_state.get("power")) == "OFF":
            current_state["mode"] = "꺼짐"
        else:
            current_state["mode"] = MODE_MAP.get(reg_map[4], "스마트")
    if 8 in reg_map:
        fan_speed = reg_map[8]
        if fan_speed == 1: current_state["fan_percentage"] = "1"
        elif fan_speed == 2: current_state["fan_percentage"] = "2"
        elif fan_speed == 3: current_state["fan_percentage"] = "3"
        else: current_state["fan_percentage"] = "0"
        
        if fan_speed == 0: current_state["fan_speed_text"] = "꺼짐"
        elif fan_speed == 4: current_state["fan_speed_text"] = "자동"
        elif fan_speed == 1: current_state["fan_speed_text"] = "약풍"
        elif fan_speed == 2: current_state["fan_speed_text"] = "중풍"
        elif fan_speed == 3: current_state["fan_speed_text"] = "강풍"
        else: current_state["fan_speed_text"] = "약풍"

    if 6 in reg_map and 7 in reg_map:
        hum_mode = reg_map[6]
        hum_val = reg_map[7]
        if hum_mode == 0: target_humidity = "에코"
        elif hum_mode == 1: target_humidity = "쾌적"
        elif hum_mode == 2: target_humidity = "건조"
        else: target_humidity = f"{hum_val}%"
        current_state["target_humidity"] = target_humidity
        
    if 13 in reg_map: current_state["ra_temp"] = parse_int16(reg_map[13])
    if 14 in reg_map: current_state["ra_humidity"] = reg_map[14]
    if 16 in reg_map: current_state["co2"] = reg_map[16]
    if 17 in reg_map: current_state["pm10"] = reg_map[17]
    if 18 in reg_map: current_state["pm25"] = reg_map[18]
    if 20 in reg_map: current_state["oa_temp"] = parse_int16(reg_map[20])
    if 21 in reg_map: current_state["oa_humidity"] = reg_map[21]

    for k, v in current_state.items():
        if last_state.get(k) != v:
            client.publish(f"humicon/state/{k}", str(v), retain=True)
            last_state[k] = v

def process_frame_06(client, reg_addr, reg_val):
    logging.info(f"Sniffed Write (0x06): Address {reg_addr}, Value {reg_val}")
    
    if reg_addr == 1:
        power = "ON" if reg_val == 1 else "OFF"
        if last_state.get("power") != power:
            client.publish("humicon/state/power", power, retain=True)
            last_state["power"] = power
            if power == "OFF":
                client.publish("humicon/state/mode", "꺼짐", retain=True)
                last_state["mode"] = "꺼짐"
    elif reg_addr == 2:
        mode = MODE_MAP.get(reg_val, "스마트")
        if last_state.get("power") == "ON" and last_state.get("mode") != mode:
            client.publish("humicon/state/mode", mode, retain=True)
            last_state["mode"] = mode
    elif reg_addr == 5:
        if reg_val == 1: pct_str = "1"; text = "약풍"
        elif reg_val == 2: pct_str = "2"; text = "중풍"
        elif reg_val == 3: pct_str = "3"; text = "강풍"
        elif reg_val == 4: pct_str = "0"; text = "자동"
        else: pct_str = "0"; text = "꺼짐"
        
        if last_state.get("fan_percentage") != pct_str:
            client.publish("humicon/state/fan_percentage", pct_str, retain=True)
            last_state["fan_percentage"] = pct_str
        
        if last_state.get("fan_speed_text") != text:
            client.publish("humicon/state/fan_speed_text", text, retain=True)
            last_state["fan_speed_text"] = text
    elif reg_addr == 3:
        mode = "에코"
        if reg_val == 0: mode = "에코"
        elif reg_val == 1: mode = "쾌적"
        elif reg_val == 2: mode = "건조"
        elif reg_val == 3: return # wait for address 4
        client.publish("humicon/state/target_humidity", mode, retain=True)
        last_state["target_humidity"] = mode
    elif reg_addr == 4:
        mode = f"{reg_val}%"
        client.publish("humicon/state/target_humidity", mode, retain=True)
        last_state["target_humidity"] = mode

def sniffer_loop(mqtt_client):
    global sock, last_start_addr_03, last_start_addr_04
    buffer = bytearray()
    
    while True:
        if sock is None:
            time.sleep(1)
            continue
            
        try:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("Socket closed by remote")
            buffer.extend(chunk)
            
            i = 0
            while i < len(buffer) - 4:
                # 0x06 Frame: [01] [06]
                if buffer[i:i+2] == b'\x01\x06':
                    frame_len = 8
                    if len(buffer) >= i + frame_len:
                        frame = buffer[i:i+frame_len]
                        crc_calc = crc16(frame[:-2])
                        crc_recv = frame[-2] | (frame[-1] << 8)
                        if crc_calc == crc_recv:
                            reg_addr, reg_val = struct.unpack(">HH", frame[2:6])
                            process_frame_06(mqtt_client, reg_addr, reg_val)
                            i += frame_len
                            continue
                
                # 0x10 Frame (Write Multiple) from Roomcon
                if buffer[i:i+2] == b'\x01\x10':
                    if len(buffer) >= i + 7:
                        byte_count = buffer[i+6]
                        frame_len = 7 + byte_count + 2
                        if len(buffer) >= i + frame_len:
                            frame = buffer[i:i+frame_len]
                            crc_calc = crc16(frame[:-2])
                            crc_recv = frame[-2] | (frame[-1] << 8)
                            if crc_calc == crc_recv:
                                start_addr, count = struct.unpack(">HH", frame[2:6])
                                logging.info(f"Sniffed Write Multiple (0x10): Start Addr {start_addr}, Count {count}")
                                # We can process it similarly to 0x03 response data
                                process_frame_03(mqtt_client, start_addr, byte_count, frame[7:-2])
                                i += frame_len
                                continue

                # 0x03 or 0x04 Frame (Request or Response)
                if buffer[i:i+2] in [b'\x01\x03', b'\x01\x04']:
                    func_code = buffer[i+1]
                    
                    # Check if it's a Request (8 bytes: 01 0X StartH StartL CountH CountL CRCL CRCH)
                    if len(buffer) >= i + 8:
                        frame_req = buffer[i:i+8]
                        if crc16(frame_req[:-2]) == (frame_req[-2] | (frame_req[-1] << 8)):
                            start_addr, count = struct.unpack(">HH", frame_req[2:6])
                            if func_code == 3: last_start_addr_03 = start_addr
                            if func_code == 4: last_start_addr_04 = start_addr
                            i += 8
                            continue
                            
                    # Check if it's a Response (3 + ByteCount + 2)
                    byte_count = buffer[i+2]
                    frame_len = 3 + byte_count + 2
                    if len(buffer) >= i + frame_len:
                        frame_res = buffer[i:i+frame_len]
                        crc_calc = crc16(frame_res[:-2])
                        crc_recv = frame_res[-2] | (frame_res[-1] << 8)
                        if crc_calc == crc_recv:
                            if func_code == 3:
                                process_frame_03(mqtt_client, 0, byte_count, frame_res[3:-2])
                            elif func_code == 4:
                                process_frame_04(mqtt_client, 0, byte_count, frame_res[3:-2])
                            i += frame_len
                            continue
                            
                # No match, advance 1 byte
                i += 1
                
            if i > 0:
                buffer = buffer[i:]
                
            if len(buffer) > 4096:
                buffer.clear()
                
        except Exception as e:
            logging.error(f"Sniffer socket error: {e}")
            mqtt_client.publish("humicon/state/availability", "offline", retain=True)
            with socket_lock:
                if sock:
                    sock.close()
                    sock = None
            connect_ew11(mqtt_client)

def active_polling_loop():
    global sock, last_write_time
    # We will alternate between reading Holding Registers (0x03) and Input Registers (0x04)
    # 0x03: Start 0 (40001), Count 6
    # 0x04: Start 0 (30001), Count 22
    
    def send_read_request(func_code, start_addr, count):
        frame = struct.pack(">BBHH", 1, func_code, start_addr, count)
        crc = crc16(frame)
        frame += struct.pack("<H", crc)
        with socket_lock:
            if sock:
                try:
                    sock.sendall(frame)
                except Exception as e:
                    pass

    while True:
        if sock is not None:
            # If a write was sent recently, pause polling to allow Mainboard to process it
            if time.time() - last_write_time < 2.0:
                time.sleep(0.5)
                continue

            # Poll Holding Registers (Mode, Humidity Mode, Humidity SetVal, Fan, etc.)
            send_read_request(3, 0, 6)
            time.sleep(1.0)
            
            # Poll Input Registers (Temperatures, PM, CO2, etc.)
            if time.time() - last_write_time >= 2.0:
                send_read_request(4, 0, 22)
            time.sleep(2.0)
        else:
            time.sleep(1)

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    logging.info("Starting Humicon Hybrid Daemon...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    # Start MQTT Loop in background thread
    client.loop_start()

    # Publish offline initially until connected
    client.publish("humicon/state/availability", "offline", retain=True)

    # Connect EW11 Socket
    connect_ew11(client)

    # Start Active Polling Thread
    poll_thread = threading.Thread(target=active_polling_loop, daemon=True)
    poll_thread.start()

    # Run sniffer in main thread
    sniffer_loop(client)

if __name__ == "__main__":
    main()

