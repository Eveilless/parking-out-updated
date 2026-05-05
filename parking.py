import os
import sys
import glob
import shutil
from dotenv import load_dotenv

from core.controller import ParkingOutController
from devices.modbus_manager import ModbusManager
from devices.printer_manager import PrinterManager
from devices.serial_readers import EmoneyReader, RfidReader, QrReader
import ui

def main():
    print("🚀 Memulai Sistem Parking Out (Refactored)...")
    
    env_files = glob.glob('/media/pi/*/.env')
    if not env_files:
        print("ERROR: File .env tidak ditemukan di /media/pi/. Pastikan flashdisk terpasang.")
        sys.exit(1)

    ENV_PATH = env_files[0]
    print(f"Konfigurasi ditemukan di: {ENV_PATH}")

    project_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    try:
        shutil.copy2(ENV_PATH, project_env)
        print("✅ File .env berhasil di-copy ke direktori project")
    except Exception as e:
        print(f"⚠️ Peringatan: Gagal menyalin .env: {e}")

    load_dotenv(dotenv_path=project_env, override=True)
    
    # 1. Inisialisasi Perangkat Hardware
    modbus = ModbusManager()
    printer = PrinterManager()
    emoney = EmoneyReader()
    rfid = RfidReader()
    qr = QrReader()
    
    # 2. Inisialisasi UI
    main_widget = ui.show_ui()
    
    # 3. Inisialisasi Controller (State Machine Utama)
    controller = ParkingOutController(
        modbus=modbus,
        printer=printer,
        emoney=emoney,
        rfid=rfid,
        qr=qr,
        ui_manager=ui
    )
    
    # 4. Jalankan Sistem
    try:
        controller.start()
        print("✅ Sistem berjalan. Menunggu kendaraan di pintu keluar...")
        # Render UI loop (blocking)
        ui.app.exec_()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown...")
    finally:
        controller.stop()

if __name__ == "__main__":
    main()
