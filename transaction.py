import requests  # type: ignore
import logging
import hashlib
import serial  # type: ignore
import time
import json
import os
import pytz
from datetime import datetime
from handlers import serial_handler
import utils
import config
from utils import read_json_session, delete_json_session, get_card_type
# from handlers import oled_handler

# List transaction for settlement
transaction_list = []

config.load_config()

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
MAX_RETRIES = 5  # Total attempts = initial + 2 retries
attempt = 0
result = None


def validate_ticket(qr_data):
    """Memvalidasi tiket ke server."""
    try:
        url = os.getenv("SERVER") + os.getenv("VALIDATE_TICKET")
        iddev = os.getenv("IDLOOP1")
        
        response = requests.post(url,
                                 json={"ticket": qr_data, "iddev": iddev}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            with open(os.getenv('ACTIVE_TRANSACTION_FILE'), "w") as file:
                json.dump(data.get("ticket", {}), file, indent=4)

            return True, data.get("ticket", {})
        else:
            return False, data
    except Exception as e:
        logging.error(f"Error validating ticket: {e}")
        print(str(e))
        return False, "Ticket tidak valid"

    return False, "Unknown error"  # ✅ Tambahkan ini


def validate_rfid(rfid_data):
    """Memvalidasi RFID ke server."""
    try:
        url = os.getenv("SERVER") + os.getenv("VALIDATE_RFID")
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url,
                                 json={"rfid": rfid_data,
                                       "iddev": os.getenv("IDLOOP1")},
                                 headers=headers,
                                 timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            return True, data.get('transaction', {})
        else:
            return False, {"message": data.get("message", "Terjadi error")}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error validating RFID: {e}")
        return False, {"message": "Error Koneksi ke server"}


def validate_emoney(card_number):
    """Memeriksa transaksi e-money ke server."""

    try:
        url = os.getenv('SERVER') + os.getenv('VALIDATE_EMONEY')
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url,
                                 json={"iddev": os.getenv("IDLOOP1"),
                                       "card_number": card_number},
                                 headers=headers,
                                 timeout=15
                                 )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            # Simpan data transaksi ke file
            with open(os.getenv('ACTIVE_TRANSACTION_FILE'), "w") as file:
                json.dump(data.get("ticket", {}), file, indent=4)
                print("Saved transaction file")

            return True, data.get("ticket", {})
        else:
            return False, {"message": data.get("message", "Terjadi error")}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking e-money transaction: {e}")
        return False, {"message": "Error Koneksi ke server"}


def is_port_in_use(port):
    """Check if the specified serial port is in use."""
    try:
        with serial.Serial(port, 38400, timeout=0.1) as test_port:
            return False
    except serial.SerialException as e:
        if "already in use" in str(e).lower() or "access is denied" in str(e).lower():
            return True
        raise


def generate_deduct_command(amount):
    try:
        if not isinstance(amount, int) or amount < 0 or amount > 2**32 - 1:
            raise ValueError(
                f"Invalid amount: {amount}. Must be a positive integer within 0 to 2^32-1.")

        now = datetime.now(JAKARTA_TZ)
        date_bcd = bytes.fromhex(now.strftime('%d%m%Y'))
        time_bcd = bytes.fromhex(now.strftime('%H%M%S'))
        deduct_amount = amount.to_bytes(4, "big")
        timeout_bcd = bytes.fromhex(os.getenv("TIMEOUT_DEDUCT", "0015"))

        command_body = bytes.fromhex(
            "EF0103") + date_bcd + time_bcd + deduct_amount + timeout_bcd
        data_length = len(command_body)
        length_bytes = bytes([data_length >> 8, data_length & 0xFF])
        lrc_value = calculate_lrc(length_bytes + command_body)

        deduct_command = b"\x02" + length_bytes + command_body + lrc_value
        return deduct_command
    except ValueError as e:
        print(f"Error in generate_deduct_command: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error in generate_deduct_command: {e}")
        raise


def attempt_deduction(serial_emoney):
    global attempt
    try:
        # if is_port_in_use(os.getenv('SERIAL_PORT')):
        #     result = {"success": False,
        #               "message": f"Port {os.getenv('SERIAL_PORT')} is already in use", "data": None}
        #     print(json.dumps(result))
        #     return result

        with open(os.getenv('ACTIVE_TRANSACTION_FILE'), 'r') as file:
            ticket_data = json.load(file)

        if not ticket_data:
            result = {"success": False,
                      "message": "Tidak ada transaksi", "data": None}
            print(json.dumps(result))
            return result

        amount = int(float(ticket_data.get("total_price", 0)))
        # amount = int(1000000)

        if amount <= 0:
            result = {"success": False,
                      "message": "Amount invalid", "data": None}
            print(json.dumps(result))
            return result

        deduct_command = generate_deduct_command(amount)
        print(f"Deduct command (hex): {deduct_command.hex().upper()}")

        # with serial.Serial(
        #     port=os.getenv('SERIAL_PORT'),
        #     baudrate=38400,
        #     timeout=1,
        #     parity=serial.PARITY_NONE,
        #     stopbits=serial.STOPBITS_ONE,
        #     bytesize=serial.EIGHTBITS
        # ) as emoney:
        print(f"Serial port opened: {serial_emoney.name}")
        print(f"Deduct command: {deduct_command}")
        serial_emoney.write(deduct_command)
        serial_emoney.flush()
        print(f"Command sent: {deduct_command.hex().upper()}")

        # for i in range(10):
        #     print(f"Waiting for response... ({i+1}/10)")
        #     time.sleep(1)
        #     response = emoney.read(2048)
        #     if response:
        #         break

        response = b""
        total_timeout = 10.0
        inter_byte_timeout = 0.2
        start_time = time.time()
        last_byte_time = start_time

        print("Waiting for response...")
        while time.time() - start_time < total_timeout:
            # Cek apakah ada data di buffer
            bytes_to_read = serial_emoney.in_waiting

            if bytes_to_read > 0:
                # Jika ada, baca semua yang ada di buffer
                chunk = serial_emoney.read(bytes_to_read)
                response += chunk
                # Reset timer "jeda antar byte"
                last_byte_time = time.time()
                print(f"Received chunk: {chunk.hex().upper()}")

            # Cek apakah kita sudah mulai menerima sesuatu
            if response:
                # Jika ya, cek apakah jeda antar-byte sudah terlampaui
                if time.time() - last_byte_time > inter_byte_timeout:
                    # Sudah lebih dari 200ms tidak ada data baru
                    print(
                        "Inter-byte timeout reached. Assuming transmission complete.")
                    break  # Keluar dari loop while

            time.sleep(0.01)  # Cek buffer setiap 10ms

            # Setelah loop selesai, cek hasilnya
        print(
            f"Final raw response ({len(response)} bytes): {response.hex().upper()}")

        if not response:
            return {"success": False, "message": "No card detected"}

        response_hex = response.hex().upper().strip()
        print(f"Response deduct: {response_hex}")

        ERROR_CODES = {
            "011001": {"message": "Kartu tidak dikenali", "extract": False},
            "011002": {"message": "Timeout: Silahkan tap ulang kartu!", "extract": False},
            "011003": {"message": "Perangkat di-reset karena error!", "extract": False, "reset_device": True},
            "011004": {"message": "Saldo tidak cukup", "extract": True, "type_idx": (12, 14), "num_idx": (16, 32)},
            "011005": {"message": "Transaksi Terputus", "extract": True, "type_idx": (14, 16), "num_idx": (16, 32)},
            "011006": {"message": "Gunakan kartu sebelumnya", "extract": True, "type_idx": (14, 16), "num_idx": (16, 32)},
            "011007": {"message": "Deduct interval kurang dari 2 detik", "extract": True, "type_idx": (14, 16), "num_idx": (16, 32)},
        }

        if '000000' in response_hex:
            with open(os.getenv('ACTIVE_TRANSACTION_FILE'), 'r', encoding='utf-8') as file:
                transaction = json.load(file)

            print(json.dumps(transaction))
            print(response_hex)

            card_data = {
                "card_type": get_card_type(int(response_hex[14:16], 16)),
                "card_number": response_hex[54:70],
                "merchant_id": response_hex[16:32],
                "terminal_id": response_hex[32:40],
                "amount": int(response_hex[70:78], 16),
                "balance": int(response_hex[78:86], 16),
            }
            print(f"Card data: {json.dumps(card_data)}")

            plate = ""
            if os.path.exists("lpr.txt"):
                with open("lpr.txt", "r") as f:
                    lines = f.readlines()
                    if lines:
                        plate = lines[0].strip()
                    else:
                        print("File lpr.txt kosong, tidak ada data plat nomor")

            data_translog = {
                "ticket_code": transaction.get("ticket_code", ""),
                "transaction": transaction,
                "translog": response_hex,
                "plate": plate,
                "card_data": card_data,
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            with open("translog/" + transaction.get("ticket_code", "") + ".json", "w") as file:
                json.dump(data_translog, file, indent=4)

            attempt = 0
            return {
                "success": True,
                "code": "200",
                "message": "Transaksi berhasil",
                "data": card_data,
                "translog": response_hex,
                "transaction": transaction,
                "plate": plate
            }

        for code, config in ERROR_CODES.items():
            if code in response_hex:
                print(config["message"])
                
                if config.get("reset_device"):
                    serial_emoney.close()
                    time.sleep(1)
                    serial_handler.initialize_device()

                card_data = None
                if config.get("extract"):
                    t_start, t_end = config["type_idx"]
                    n_start, n_end = config["num_idx"]
                    card_data = {
                        "card_type": get_card_type(int(response_hex[t_start:t_end], 16)),
                        "card_number": response_hex[n_start:n_end]
                    }

                return {
                    "success": False,
                    "code": code,
                    "message": config["message"],
                    "data": card_data
                }

        return {
            "success": False,
            "code": None,
            "message": f"Unrecognized short response: {response_hex}",
            "data": None
        }
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        result = {"success": False,
                  "message": f"Serial error: {e}", "data": None}
        print(json.dumps(result))
        return result
    except Exception as e:
        print(f"Error: {e}")
        result = {"success": False, "message": f"Error: {e}", "data": None}
        print(json.dumps(result))
        return result


def process_deduction():
    """Proses pengurangan saldo e-money."""
    # ticket_data = read_json_session(config.ACTIVE_TRANSACTION_FILE)
    try:
        with open(config.ACTIVE_TRANSACTION_FILE, "r") as file:
            ticket_data = json.load(file)
    except Exception as e:
        logging.error(f"Gagal membaca data transaksi: {e}")
        return False, "Gagal membaca transaksi"

    if not ticket_data:
        logging.warning("No active transaction found.")
        return False, "Tidak ada transaksi berjalan"

    print(json.dumps(ticket_data))
    # raw_total_price = ticket_data.get("total_price")
    # logging.info(
    #     f"DEBUG: raw_total_price from ticket_data: '{raw_total_price}' (type: {type(raw_total_price)})")

    amount = int(float(ticket_data.get("total_price", 0)))
    print(f"amount: {amount}")
    if amount <= 0:
        logging.warning("Invalid ticket amount.")
        return False, "Ticket tidak valid"

    try:
        with serial.Serial(config.SERIAL_PORT, config.BAUDRATE, timeout=10) as ser:
            for _ in range(int(config.MAX_RETRIES)):
                result, message = deduct(ser, amount)
                if result:
                    return True, message
                time.sleep(1)
    except serial.SerialException as e:
        logging.error(f"Error processing deduction: {e}")
        return False, f"Error komunikasi dengan perangkat\n\nSilahkan coba lagi"

    return False, "Gagal melakukan transaksi \nSilahkan coba lagi"


def load_json():
    try:
        with open(config.ACTIVE_TRANSACTION_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return None


def calculate_lrc(data):
    """Calculate LRC by XORing all bytes."""
    lrc = 0
    for byte in data:
        lrc ^= byte
    return bytes([lrc])


def build_command(payload_hex: str) -> bytes:
    payload = bytes.fromhex(payload_hex)
    length = len(payload)
    frame = b'\x02' + bytes([length >> 8, length & 0xFF]) + payload
    frame += calculate_lrc(frame)
    return frame


def update_translog(ticket, translog, card_data, plate, end_time=None):
    try:
        url = os.getenv('SERVER') + "/update-translog"
        headers = {'Content-Type': 'application/json'}

        safe_card_data = card_data or {}

        response = requests.post(url, json={
            "ticket_code": ticket.get("ticket_code"),
            "total_time": ticket.get("total_time"),
            "total_price": ticket.get("total_price"),
            "translog": translog,
            "emoney_card_number": safe_card_data.get("card_number", ""),
            "emoney_card_type": safe_card_data.get("card_type", ""),
            "mid": safe_card_data.get("merchant_id", ""),
            "tid": safe_card_data.get("terminal_id", ""),
            "plat_out": plate,
            "end_time": end_time
        },
            headers=headers,
            timeout=10)

        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            print("Success update translog")
            logging.info("Success update translog")
            return True, "Success update translog"
        else:
            print(f"Error update translog: {json.dumps(data.get('message'))}")
            logging.info(
                f"Error update translog: {json.dumps(data.get('message'))}")
            return False, "Error update translog: " + json.dumps(data.get('message'))

    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking e-money transaction: {e}")
        return False, "Error komunikasi dengan server"


def deduct(ser, amount):
    """Mengurangi saldo kartu e-money"""
    print(f"Deduct amount: {amount}")

    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz)

    date_bcd = bytes.fromhex(now.strftime('%d%m%Y'))
    time_bcd = bytes.fromhex(now.strftime('%H%M%S'))
    deduct_amount = amount.to_bytes(4, "big")
    timeout_bcd = bytes.fromhex(config.TIMEOUT_DEDUCT)

    command_body = bytes.fromhex(
        "EF0103") + date_bcd + time_bcd + deduct_amount + timeout_bcd
    data_length = len(command_body)
    length_bytes = bytes([data_length >> 8, data_length & 0xFF])
    lrc_value = calculate_lrc(length_bytes + command_body)

    deduct_command = b"\x02" + length_bytes + command_body + lrc_value

    logging.info(f"📤 Sending command: {deduct_command.hex().upper()}")
    ser.write(deduct_command)
    ser.flush()

    time.sleep(2)
    response = ser.read(128)

    if response:
        response_hex = response.hex().upper()
        logging.info(f"📥 Response: {response_hex}")
        print(f"Response deduct: {response_hex}")

        if len(response) < 47:
            if response_hex == "0200040001100217":
                return False, "Timeout: Silahkan scan ulang tiket!"
            if response_hex == "0200040201100314":
                if ser and ser.is_open:
                    ser.close()
                    time.sleep(1)
                    serial_handler.initialize_device()
                    return False, "Perangkat di-reset karena error!"
                return False, "Error: Respon terlalu pendek!"
        else:
            with open(config.ACTIVE_TRANSACTION_FILE, 'r', encoding='utf-8') as file:
                transaction = json.load(file)

            print(json.dumps(transaction))
            print(response_hex)

            success, response = update_translog(
                transaction.get('ticket_code'), response_hex)
            if success:
                print("Success update log")
                logging.info("Success update log")
                # oled_handler.print_oled("Success update translog")
                return True, "Transaksi berhasil"
            else:
                print("Error update log")
                logging.info("Error update log")
                # oled_handler.print_oled("Error update translog")
                return False, response
    else:
        logging.warning("No response received from device!")
        return False, "Error: Tidak ada respon dari perangkat!"


def generate_signature(merchant_key, merchant_code, ref_no, amount, currency):
    source_string = f"||{merchant_key}||{merchant_code}||{ref_no}||{amount}||{currency}||"

    signature = hashlib.sha256(source_string.encode('utf-8')).hexdigest()

    return signature


def request_qris_payment(ref_no, amount):
    merchant_key = os.getenv('MERCHANT_KEY')
    merchant_code = os.getenv('MERCHANT_CODE')
    currency = "IDR"

    signature_code = generate_signature(
        merchant_key, merchant_code, ref_no, amount, currency)

    headers = {'Content-Type': 'application/json'}
    payload = {
        "APIVersion": "2.0",
        "MerchantCode": merchant_code,
        "PaymentId": "120",
        "Currency": currency,
        "RefNo": ref_no,
        "Amount": amount,
        "ProdDesc": "Parking Fee",
        "UserName": "Technical Support",
        "UserEmail": "techsupp@ipay88.co.id",
        "UserContact": "081234567890",
        "Remark": "",
        "Lang": "iso-8859-1",
        "RequestType": "seamless",
        "ResponseURL": "https://sandbox.ipay88.co.id/epayment/fujipaystatusv2.asp",
        "BackendURL": "http://sandbox.ipay88.co.id/ePayment/testing/RequestForm_savetemp.asp",
        "Signature": signature_code
    }

    print(json.dumps(payload))

    url = "https://sandbox.ipay88.co.id/ePayment/WebService/PaymentAPI/Checkout"

    try:
        response = requests.post(
            url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if str(data.get("Code")) == "1":
            return data.get("VirtualAccountAssigned")
        else:
            logging.error(f"Error dari API iPay88: {data.get('Message')}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Gagal melakukan request ke iPay88: {e}")
        return False
