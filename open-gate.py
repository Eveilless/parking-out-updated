import os
import json
import requests
import time
from dotenv import load_dotenv
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType

load_dotenv("/home/pi/parking-out/.env")

HOST = os.getenv("ETH_HOST")
PORT = os.getenv("ETH_PORT", 502)
TIMEOUT = 3

SLAVE_ID_OUTPUT = 2
COIL_ADDRESS_OUTPUT = 0
COIL_BARRIER_GATE = 0

client = ModbusTcpClient(
    host=HOST,
    port=PORT,
    framer=FramerType.RTU,
    timeout=TIMEOUT,
    retries=1
)

if client.connect():
    print(f"✅ Connected to {HOST}:{PORT}")

def write_coil(address, state):
    try:
        # PENTING: Koneksi ulang jika terputus (karena tidak ada 'lock')
        if not client.is_socket_open():
            client.connect()
            
        result = client.write_coil(
            address=COIL_ADDRESS_OUTPUT + address,
            value=bool(state),
            slave=SLAVE_ID_OUTPUT
        )
        if not result.isError():
            print(f"✅ Coil {address} set to {'ON' if state else 'OFF'}")
            return True
        else:
            print(f"❌ Write error: {result}")
            return False
    except Exception as e:
        print(f"❌ Write exception: {e}")
        # Coba tutup koneksi agar bisa 'reconnect' di panggilan berikutnya
        client.close()
        return False
    
server = os.getenv('SERVER')
gate_id = os.getenv('IDLOOP1')
url = f"{server}/gate/open_qris?gate_id={gate_id}"
url_close = f"{server}/gate/close_qris?gate_id={gate_id}"

while True:
    try:
        response = requests.get(url, timeout=3)
        print(f"Polling server... Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == "success":
                print("✅ Gate open command received!")
                
                # 1. Buka palang
                write_coil(COIL_BARRIER_GATE, True)
                
                # 2. Beri tahu server (dan cek responsnya)
                response_close = requests.get(url_close, timeout=3)
                
                # PERBAIKAN: Cek 'response_close'
                if response_close.status_code == 200: 
                    print("✅ Success close gate")
                else:
                    print(f"❌ Failed to close gate API: {response_close.status_code}")

                # 3. Tunggu 5 detik agar mobil lewat SEBELUM menutup
                print("Palang terbuka, menunggu 5 detik...")
                time.sleep(5)
                
                # 4. Tutup palang
                write_coil(COIL_BARRIER_GATE, False)
                
    except Exception as e:
        print(f"Error: {e}")
    
    # PERBAIKAN: SELALU sleep di akhir loop
    time.sleep(1) # Poll setiap 1 detik