import serial
import time
import os

class SerialReader:
    def __init__(self, port_env, baudrate_env=9600, name="Reader"):
        self.port = os.getenv(port_env)
        try:
            self.baudrate = int(os.getenv(baudrate_env, 9600))
        except (ValueError, TypeError):
            self.baudrate = 9600
            
        self.name = name
        self.serial_conn = None

    def connect(self):
        if not self.port:
            return False
        if self.serial_conn and self.serial_conn.is_open:
            return True
            
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"✅ {self.name} connected on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"❌ {self.name} connection failed: {e}")
            self.serial_conn = None
            return False

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print(f"🔌 {self.name} disconnected")
            self.serial_conn = None

    def is_connected(self):
        return self.serial_conn is not None and self.serial_conn.is_open

    def has_data(self):
        if self.is_connected():
            try:
                return self.serial_conn.in_waiting > 0
            except:
                return False
        return False

    def reset_buffer(self):
        if self.is_connected():
            try:
                self.serial_conn.reset_input_buffer()
            except:
                pass


class EmoneyReader(SerialReader):
    def __init__(self):
        # E-Money typically uses 38400
        super().__init__('SERIAL_PORT', 'BAUDRATE', "E-Money Reader")
        
    def read_balance(self):
        """Baca balance dari kartu e-money."""
        # Logika pembacaan balance di-handle melalui handlers.serial_handler.check_balance
        # atau di transaction.py. Di sini hanya mengembalikan koneksi serialnya
        pass

class RfidReader(SerialReader):
    def __init__(self):
        super().__init__('SERIAL_PORT_RFID', 'BAUDRATE_RFID', "RFID Reader")
        
    def read_data(self):
        if not self.is_connected() or not self.has_data():
            return None
            
        try:
            raw_data = self.serial_conn.readline()
            if len(raw_data) < 3:
                return None
                
            data = raw_data.decode("utf-8", errors="ignore").strip()
            if data.startswith('\x02'): data = data[1:]
            if data.endswith('\x03'): data = data[:-1]
            data = data.strip()
            
            if len(data) <= 1:
                return None
                
            data_integer = int(data, 16)
            data_str = str(data_integer)[0:10].zfill(10)
            return data_str
        except Exception as e:
            print(f"Error parsing RFID: {e}")
            return None

class QrReader(SerialReader):
    def __init__(self):
        super().__init__('SERIAL_PORT_QR', 'BAUDRATE_QR', "QR Reader")
        
    def read_data(self):
        if not self.is_connected() or not self.has_data():
            return None
            
        try:
            data = self.serial_conn.readline().decode('utf-8').strip()
            return data if data else None
        except Exception as e:
            print(f"Error parsing QR: {e}")
            return None
