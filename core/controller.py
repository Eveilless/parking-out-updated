import threading
import time
import os
import json
import logging
from handlers import sound_handler, oled_handler, serial_handler
from transaction import validate_ticket, validate_emoney, validate_rfid, update_translog, attempt_deduction

class ParkingOutController:
    def __init__(self, modbus, printer, emoney, rfid, qr, ui_manager):
        self.modbus = modbus
        self.printer = printer
        self.emoney = emoney
        self.rfid = rfid
        self.qr = qr
        self.ui = ui_manager
        
        self.running = False
        self.vehicle_detected = False
        self.is_busy = False
        self.transaction_successful = False
        self.state_lock = threading.Lock()
        
        self.welcome_text = os.getenv("WELCOME_TEXT", "SELAMAT DATANG BHC PARKING SYSTEM")
        self.ip_address = "127.0.0.1"

    def print_to_oled(self, row_one='', row_two='', row_three=''):
        logging.info(row_one)
        oled_handler.print_oled(self.ip_address, row_one, row_two, row_three)

    def start(self):
        self.running = True
        self.modbus.connect()
        
        # Connect serial devices
        self.emoney.connect()
        self.rfid.connect()
        self.qr.connect()

        # Start background threads
        threading.Thread(target=self._modbus_loop, daemon=True).start()
        threading.Thread(target=self._emoney_loop, daemon=True).start()
        threading.Thread(target=self._rfid_loop, daemon=True).start()
        threading.Thread(target=self._qr_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.modbus.disconnect()
        self.emoney.disconnect()
        self.rfid.disconnect()
        self.qr.disconnect()

    def set_ui_text(self, text, mode="welcome"):
        if self.ui and self.ui.main_widget:
            self.ui.main_widget.mode = mode
            if mode == "welcome":
                self.ui.main_widget.set_welcome_text(text)
            self.ui.main_widget.update()

    def release_system(self, success=False):
        """Melepaskan state lock dan me-reset sistem jika gagal, atau menahan lock jika sukses hingga kendaraan pergi"""
        with self.state_lock:
            self.transaction_successful = success
            if not success:
                self.is_busy = False
                self.modbus.close_gate()
                print("Sistem SIAP kembali (Transaksi Gagal/Dibatalkan).")
            else:
                print("Transaksi SUKSES. Sistem menahan state sibuk hingga kendaraan pergi.")

    def _modbus_loop(self):
        prev_button = None
        while self.running:
            try:
                inputs = self.modbus.read_inputs()
                if inputs:
                    loop_sensor = inputs[self.modbus.reg_loop_sensor]
                    button = inputs[self.modbus.reg_button_ticket]
                    
                    # Logic: Loop Sensor
                    if loop_sensor == 1:
                        with self.state_lock:
                            if not self.vehicle_detected:
                                self.vehicle_detected = True
                                sound_handler.play_vehicle_detected_sound("../assets/print_ticket.mp3")
                                self.print_to_oled("Vehicle detected")
                                self.set_ui_text("SILAHKAN TEMPELKAN KARTU ATAU SCAN TIKET")
                                
                                self.emoney.reset_buffer()
                                self.rfid.reset_buffer()
                                self.qr.reset_buffer()
                    else:
                        if self.vehicle_detected:
                            print("Kendaraan meninggalkan loop sensor")
                            self.set_ui_text(self.welcome_text.upper())
                            with self.state_lock:
                                self.is_busy = False
                                self.transaction_successful = False
                                self.vehicle_detected = False
                                self.modbus.close_gate()

                    # Logic: Reprint Button
                    if prev_button == 0 and button == 1:
                        with self.state_lock:
                            if not self.vehicle_detected:
                                print("Tombol ditekan tapi tidak ada mobil.")
                            elif self.is_busy and self.transaction_successful:
                                threading.Thread(target=self._handle_reprint, daemon=True).start()
                            else:
                                print("Scan tiket dahulu sebelum cetak.")
                                
                    prev_button = button

            except Exception as e:
                print(f"Modbus loop error: {e}")
            time.sleep(0.5)

    def _handle_reprint(self):
        active_file = os.getenv('ACTIVE_TRANSACTION_FILE')
        if active_file and os.path.exists(active_file):
            with open(active_file, "r") as f:
                data = json.load(f)
            self.printer.print_invoice(data)

    def _emoney_loop(self):
        while self.running:
            if not self.emoney.is_connected():
                self.emoney.connect()
                time.sleep(3)
                continue
                
            if not self.vehicle_detected:
                time.sleep(0.05)
                continue
                
            with self.state_lock:
                if self.is_busy:
                    time.sleep(0.1)
                    continue

            # Check card via serial handler (blocking call)
            success_read, card_data, conn = serial_handler.check_balance(self.emoney.serial_conn)
            if not success_read:
                time.sleep(0.1)
                continue

            with self.state_lock:
                if self.is_busy:
                    continue
                self.is_busy = True
                self.transaction_successful = False
                
            try:
                card_number = card_data.get('card_number')
                self.set_ui_text(f"VALIDATE: {card_number}")
                
                success_val, response = validate_emoney(card_number)
                if not success_val:
                    raise ValueError(response.get("message", "Validasi Gagal"))

                with open(os.getenv('ACTIVE_TRANSACTION_FILE'), "w") as file:
                    json.dump(response, file, indent=4)

                status = response.get("status_gate")
                if status == "payed" or (status == "generated" and int(response.get('total_price') or 0) == 0):
                    self.modbus.open_gate()
                    self.set_ui_text(f"LUNAS: {card_number}")
                    update_translog(response, None, None, None)
                    self.release_system(success=True)
                elif status == "generated":
                    # Menunggu pembayaran
                    self.ui.main_widget.mode = "payment"
                    self.ui.main_widget.set_payment_data({
                        "Ticket Code": response.get('ticket_code'),
                        "Total Harga": int(response.get('total_price') or 0)
                    })
                    self.ui.main_widget.update()
                    time.sleep(2)
                    success_payment = self._handle_payment_loop()
                    self.release_system(success=success_payment)
                else:
                    raise ValueError("Status tidak dikenal")

            except Exception as e:
                self.set_ui_text(str(e).upper())
                time.sleep(2)
                self.release_system(success=False)
            finally:
                self.emoney.reset_buffer()

    def _rfid_loop(self):
        while self.running:
            if not self.rfid.is_connected():
                self.rfid.connect()
                time.sleep(3)
                continue
                
            data = self.rfid.read_data()
            if not data or not self.vehicle_detected:
                time.sleep(0.1)
                continue
                
            with self.state_lock:
                if self.is_busy:
                    continue
                self.is_busy = True
                
            try:
                self.set_ui_text(f"VALIDATE RFID: {data}")
                success_val, response = validate_rfid(data)
                
                if success_val:
                    self.modbus.open_gate()
                    self.set_ui_text(f"TERIMA KASIH: {data}")
                    self.release_system(success=True)
                else:
                    raise ValueError(response.get("message", "Validasi RFID Gagal"))
            except Exception as e:
                self.set_ui_text(str(e).upper())
                time.sleep(2)
                self.release_system(success=False)

    def _qr_loop(self):
        while self.running:
            if not self.qr.is_connected():
                self.qr.connect()
                time.sleep(3)
                continue
                
            data = self.qr.read_data()
            if not data or not self.vehicle_detected:
                time.sleep(0.1)
                continue
                
            with self.state_lock:
                if self.is_busy:
                    continue
                self.is_busy = True
                
            try:
                self.set_ui_text(f"VALIDATE: {data}")
                success_val, response = validate_ticket(data)
                
                if not success_val:
                    raise ValueError(response.get("message", "Validasi Tiket Gagal"))

                with open(os.getenv('ACTIVE_TRANSACTION_FILE'), "w") as file:
                    json.dump(response, file, indent=4)

                status = response.get("status_gate")
                if status == "payed" or (status == "generated" and int(response.get('total_price') or 0) == 0):
                    self.modbus.open_gate()
                    update_translog(response, None, None, None)
                    self.set_ui_text("LUNAS")
                    self.release_system(success=True)
                elif status == "generated":
                    virtualCode = response.get("virtual_code")
                    if virtualCode:
                        self.printer.print_qris(virtualCode)
                        
                    self.ui.main_widget.mode = "payment"
                    self.ui.main_widget.set_payment_data({
                        "Ticket Code": response.get('ticket_code'),
                        "Total Harga": int(response.get('total_price') or 0)
                    })
                    self.ui.main_widget.update()
                    time.sleep(2)
                    success_payment = self._handle_payment_loop()
                    self.release_system(success=success_payment)
                    
            except Exception as e:
                self.set_ui_text(str(e).upper())
                time.sleep(2)
                self.release_system(success=False)

    def _handle_payment_loop(self):
        payment_attempts = 0
        MAX_ATTEMPTS = 3
        
        while payment_attempts < MAX_ATTEMPTS:
            if not self.vehicle_detected:
                serial_handler.send_cancel_command(self.emoney.serial_conn)
                self.set_ui_text("TRANSAKSI DIBATALKAN")
                sound_handler.play_vehicle_detected_sound("../assets/cancel.mp3")
                time.sleep(2)
                return False

            response = attempt_deduction(self.emoney.serial_conn)
            if response and response.get('success'):
                self.modbus.open_gate()
                self.set_ui_text("PEMBAYARAN BERHASIL")
                return True
            elif response and response.get("message") != "No card detected":
                payment_attempts += 1
                remaining = MAX_ATTEMPTS - payment_attempts
                if remaining > 0:
                    self.set_ui_text(f"GAGAL. SISA {remaining} PERCOBAAN", mode="payment")
                    time.sleep(1.5)
                else:
                    self.set_ui_text("TRANSAKSI DIBATALKAN\nBATAS PERCOBAAN HABIS", mode="welcome")
                    time.sleep(2)
            time.sleep(0.2)

        serial_handler.send_cancel_command(self.emoney.serial_conn)
        sound_handler.play_vehicle_detected_sound("../assets/cancel.mp3")
        return False
