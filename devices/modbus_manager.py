import threading
import os
import time
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType
from pymodbus.exceptions import ModbusIOException

class ModbusManager:
    def __init__(self):
        self.host = os.getenv('ETH_HOST', '192.168.0.7')
        self.port = int(os.getenv('ETH_PORT', 502))
        self.timeout = 3
        
        self.slave_id_input = 1
        self.coil_address_input = 0x0081
        self.input_count = 8
        self.reg_button_ticket = 2
        self.reg_loop_sensor = 0
        
        self.slave_id_output = 2
        self.coil_address_output = 0
        self.output_count = 4
        self.coil_barrier_gate = 0
        
        self.client = None
        self.lock = threading.Lock()
        
    def connect(self):
        with self.lock:
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                framer=FramerType.RTU,
                timeout=self.timeout,
                retries=1
            )
            if self.client.connect():
                print(f"✅ Connected to Modbus {self.host}:{self.port}")
                return True
            else:
                print(f"❌ Failed to connect to Modbus {self.host}:{self.port}")
                return False
                
    def disconnect(self):
        with self.lock:
            if self.client:
                self.client.close()
                print("🔌 Modbus Connection closed")
                
    def read_inputs(self):
        with self.lock:
            try:
                if not self.client.is_socket_open():
                    self.client.connect()
                response = self.client.read_holding_registers(
                    address=self.coil_address_input,
                    count=self.input_count,
                    slave=self.slave_id_input
                )
                if response and not response.isError():
                    return response.registers
                return None
            except ModbusIOException as e:
                print(f"❌ Modbus read error: {e}")
                self.client.close()
                return None
            except Exception as e:
                print(f"❌ Modbus generic error: {e}")
                return None
                
    def write_coil(self, address, state):
        with self.lock:
            try:
                if not self.client.is_socket_open():
                    self.client.connect()
                result = self.client.write_coil(
                    address=self.coil_address_output + address,
                    value=bool(state),
                    slave=self.slave_id_output
                )
                if not result.isError():
                    print(f"✅ Coil {address} set to {'ON' if state else 'OFF'}")
                    return True
                return False
            except Exception as e:
                print(f"❌ Write coil error: {e}")
                self.client.close()
                return False

    def open_gate(self):
        """Membuka barrier gate lalu menutupnya kembali jika diperlukan (atau gate punya autoscant)"""
        # Biasanya barrier gate menggunakan sinyal pulse/trigger
        self.write_coil(self.coil_barrier_gate, True)
        
    def close_gate(self):
        self.write_coil(self.coil_barrier_gate, False)
