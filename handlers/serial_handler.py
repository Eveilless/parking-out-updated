import serial  # type: ignore
import time
import logging
import config
import os
import json
# from utils import calculate_lrc
# from handlers import oled_handler

config.load_config()


def init_serial(port, baudrate=9600, timeout=0.1, name=""):
    try:
        serial_port = serial.Serial(
            port=port,
            baudrate=baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout
        )
        print(f"Serial {name} connected")
        return serial_port, False
    except Exception as e:
        print(f"Error opening serial port {port}: {e}")
        # oled_handler.print_oled(f"Error serial {name}", "Not connected")
        return None, True


def initialize_device():
    """Menginisialisasi perangkat e-money reader."""
    try:
        with serial.Serial(os.getenv("SERIAL_PORT"), 38400, timeout=2) as ser:
            logging.info("Initializing device...")
            init_key = bytes.fromhex("FDD10CC9F79C4CC78CA15CDD4CDEBF91")
            command_prefix = b'\xEF\x01\x01'
            command_body = command_prefix + init_key
            data_length = len(command_body)
            length_bytes = data_length.to_bytes(2, 'big')

            lrc_payload = length_bytes + command_body
            lrc_value = calculate_lrc(lrc_payload)

            full_command = b'\x02' + lrc_payload + lrc_value
            logging.info(
                f"Constructed Init Command: {full_command.hex().upper()}")

            # init_command = bytes.fromhex(
            #     "020013EF0101758F40D46D95D1641448AA19B9282C0588")
            # init_command = bytes.fromhex(
            #     "020013EF0101")
            ser.write(full_command)
            ser.flush()
            time.sleep(1)
            response = ser.read_all()
            if response:
                logging.info(f"Device initialized: {response.hex().upper()}")
            else:
                logging.error("No response received during initialization.")
    except serial.SerialException as e:
        logging.error(f"Error opening serial port: {e}")


def read_qr_code(serial_qr):
    """Membaca data dari scanner QR Code."""
    try:
        if serial_qr.in_waiting:
            data = serial_qr.readline().decode('utf-8').strip()
            return data, True, serial_qr
    except (serial.SerialException, OSError):
        logging.error(f"QR Code disconnected, try to reconnect")
        print("QR Code disconnected, try to reconnect")
        try:
            serial_qr.close()
        except:
            pass

        try:
            ser = serial.Serial(config.SERIAL_PORT_QR, 9600, timeout=0.1)
            print("QR Serial reconnected.")
        except Exception as e:
            print(f"Reconnect QR failed: {e}")
            ser = None
        return None, False, ser
    return None, False, serial_qr


def read_rfid(serial_rfid):
    try:
        if serial_rfid is None or not serial_rfid.is_open:
            raise serial.SerialException("RFID Serial not open")

        data = serial_rfid.readline()
        if len(data) < 3:
            serial_rfid.flushInput()
            serial_rfid.flushOutput()
            return "", False, serial_rfid

        data = data.decode("utf-8", errors="ignore").strip()
        data = data[1:]

        if len(data) <= 1:
            return "", False, serial_rfid

        try:
            data_integer = int(data, 16)
        except ValueError:
            return "", False, serial_rfid

        data_str = str(data_integer)[0:10]
        if len(data_str) < 10:
            data_str = data_str.zfill(10)

        serial_rfid.flushInput()
        serial_rfid.flushOutput()

        print(f"RFID Data (parsed): {data_str}")
        return data_str, True, serial_rfid
    except (serial.SerialException, OSError) as e:
        print(f"RFID Serial disconnected: {e}, attempting reconnect...")
        try:
            serial_rfid.close()
        except:
            pass
        try:
            serial_rfid = serial.Serial(
                config.SERIAL_PORT_RFID, 9600, timeout=0.1)
            print("RFID Serial reconnected.")
        except Exception as e:
            print(f"Reconnect RFID failed: {e}")
            serial_rfid = None
        return "", False, serial_rfid


def read_lpr(serial_lpr):
    try:
        if serial_lpr is None or not serial_lpr.is_open:
            raise serial.SerialException("LPR Serial not open")

        data = serial_lpr.read(64)
        # print(data.hex())
        if len(data) < 5:
            serial_lpr.flushInput()
            serial_lpr.flushOutput()
            return "", False, serial_lpr

        plate, valid = parse_lpr_data(data)
        if not valid:
            print("Invalid LPR data received")
            return "", False, serial_lpr

        print(f"LPR Data (parsed): {plate}")
        return plate, True, serial_lpr
    except (serial.SerialException, OSError) as e:
        print(f"LPR Serial disconnected: {e}, attempting reconnect...")
        try:
            serial_lpr.close()
        except:
            pass
        try:
            serial_lpr = serial.Serial('/dev/ttyACM0', 9600, timeout=0.1)
            print("LPR Serial reconnected.")
        except Exception as e:
            print(f"Reconnect LPR failed: {e}")
            serial_lpr = None
        return "", False, serial_lpr


def parse_lpr_data(data: bytes):
    try:
        hex_string = data.hex().upper()
        # print(hex_string)
        # print(hex_string[0:10])
        # BB88AA03FF42453236313644414B00000000000000000000000000006402001C
        if hex_string[0:10] == "BB88AA02FF" or hex_string[0:10] == "BB88AA03FF":
            raw_plate_data = hex_string[10:]
            # print(raw_plate_data)
            raw_plate_data = raw_plate_data[:-34]
            # print(raw_plate_data)
            plate_ascii_string = bytes.fromhex(raw_plate_data).decode('ascii')
            # print(plate_ascii_string)
            clean_plate = plate_ascii_string
            return clean_plate, True
        else:
            return "", False

    except Exception as e:
        print(f"LPR parsing error: {e}")
        return "", False


def parse_emoney_simple(response_hex: str):
    try:
        response_hex = response_hex.upper().strip()
        response_len = len(response_hex)

        if response_hex == "0200040001100217":
            print("💡 Info: No card detected response.")
            return {
                "status": False,
                "code": "0200040001100217"
            }

        elif response_len == 42 and response_hex.startswith("020011"):
            print("Parsing format pendek...")
            card_type = response_hex[14:16]
            card_number = response_hex[16:32]
            balance_hex = response_hex[32:40]
            balance = int(balance_hex, 16)

            print(f"Card Number: {card_number}")
            print(f"Card Type: {card_type}")
            print(f"Balance: {balance}")

            return {
                "status": True,
                "code": response_hex,
                "card_type": card_type,
                "card_number": card_number,
                "balance": balance
            }

        elif response_hex.startswith("020004000110021702001100"):
            # Step 2: Pisahkan field
            print("Parsing format panjang...")
            card_type = response_hex[30:32]
            card_number = response_hex[32:48]
            balance_hex = response_hex[48:56]

            balance = int(balance_hex, 16)

            print(f"Card Number: {card_number}")
            print(f"Card Type: {card_type}")
            print(f"Balance: {balance}")

            return {
                "status": True,
                "code": response_hex,
                "card_type": card_type,
                "card_number": card_number,
                "balance": balance
            }
        # 3. Jika format tidak dikenali
        else:
            print(
                f"❌ Error: Format respons tidak dikenali (panjang: {response_len}).")
            print(f"   -> Respons: {response_hex}")
            return {
                "status": False,
                "code": ""
            }

    except Exception as e:
        print(f"❌ Error parsing EMoney: {e}")
        return {
            "status": False
        }


def check_balance(serial_emoney):
    try:
        if serial_emoney is None or not serial_emoney.is_open:
            raise serial.SerialException("EMoney Serial not open")

        logging.info("Checking balance...")

        current_time = time.strftime("%d%m%Y%H%M%S")
        timeout_bcd = "0002"
        command_body = bytes.fromhex("EF0102" + current_time + timeout_bcd)

        data_length = len(command_body)
        len_h = (data_length >> 8) & 0xFF
        len_l = data_length & 0xFF
        length_bytes = bytes([len_h, len_l])

        lrc_value = calculate_lrc(length_bytes + command_body)
        check_balance_command = b"\x02" + length_bytes + command_body + lrc_value

        logging.info(
            f"📤 Sending command: {check_balance_command.hex().upper()}")

        # print(f"Check balance command: {check_balance_command}")
        serial_emoney.write(check_balance_command)
        serial_emoney.flush()

#         time.sleep(2)
        response = serial_emoney.readline()
        # print(f"Read all: {response}")

        if not response:
            # print("No response received!")
            return False, "No response received", serial_emoney

        response_hex = response.hex().upper()
        print("Response:", response_hex)

        response = parse_emoney_simple(response_hex)
        if not response.get("status"):
            print("❌ Gagal memproses data EMoney (format atau LRC tidak valid)")
            return False, "Invalid EMoney data format", serial_emoney

        print(f"Card Type: {response['card_type']}")
        print(f"Card No: {response['card_number']}")
        print(f"Balance: {response['balance']}")
        print(f"Code: {response['code']}")

        card_data = {
            "code": response["code"],
            "card_type": response["card_type"],
            "card_number": response["card_number"],
            "balance": response["balance"]
        }

        print(json.dumps(card_data))

        return True, card_data, serial_emoney
    except (serial.SerialException, OSError) as e:
        logging.error(
            f"EMoney Serial disconnected: {e}, attempting reconnect...")
        try:
            serial_emoney.close()
        except:
            pass
        try:
            serial_emoney = serial.Serial(
                config.SERIAL_PORT, config.BAUDRATE, timeout=2)
            initialize_device()
            logging.info("EMoney Serial reconnected.")
        except Exception as e:
            logging.error(f"Reconnect EMoney failed: {e}")
            serial_emoney = None
        return False, "Serial reconnect failed", serial_emoney


def calculate_lrc(data):
    """Calculate LRC by XORing all bytes."""
    lrc = 0
    for byte in data:
        lrc ^= byte
    return bytes([lrc])


def send_cancel_command(serial_emoney):
    """Mengirim perintah hex untuk membatalkan proses deduct ke card reader."""
    try:
        payload = bytes.fromhex("EF0104")
        length = len(payload)
        header = b'\x02' + bytes([length >> 8, length & 0xFF])
        frame = header + payload
        lrc = calculate_lrc(frame[1:])
        full_command = frame + lrc

        logging.info(
            f"Mengirim perintah Batal Deduct (hex): {full_command.hex().upper()}")
        print(f"Cancel deduct command: {full_command.hex().upper()}")

        # Menggunakan 'with' untuk manajemen koneksi serial yang aman
        if serial_emoney is not None:
            serial_emoney.write(full_command)
            serial_emoney.flush()
        else:
            with serial.Serial(os.getenv('SERIAL_PORT'), baudrate=38400, timeout=5) as emoney_port:
                emoney_port.write(full_command)
                emoney_port.flush()
        logging.info("Perintah Batal Deduct berhasil dikirim.")

    except serial.SerialException as e:
        logging.error(f"Gagal mengirim perintah Batal Deduct: {e}")
        print(f"Gagal mengirim perintah Batal Deduct: {e}")
    except Exception as e:
        logging.error(
            f"Terjadi error tak terduga saat membatalkan deduct: {e}")
        print(
            f"Terjadi error tak terduga saat membatalkan deduct: {e}")
