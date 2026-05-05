import os
import json
from escpos.printer import Usb

class PrinterManager:
    def __init__(self):
        self.printer = None
        
    def connect(self):
        try:
            vendor_str = os.getenv('PRINTER_VENDOR')
            product_str = os.getenv('PRINTER_PRODUCT')
            
            vendor = int(vendor_str, 16) if vendor_str else None
            product = int(product_str, 16) if product_str else None
            
            if vendor and product:
                self.printer = Usb(vendor, product, timeout=5000, profile="TM-T88III")
            else:
                raise ValueError("Vendor or product ID is null")
                
            self.printer.open()
            print("✅ Printer connected")
            return True
        except Exception as e:
            print(f"⚠️ Primary printer connect error: {e}")
            try:
                # Fallback
                self.printer = Usb(0x0483, 0x5743, timeout=5000, profile="TM-T88III")
                self.printer.open()
                print("✅ Fallback printer connected")
                return True
            except Exception as fallback_e:
                print(f"❌ Fallback printer connect error: {fallback_e}")
                self.printer = None
                return False
                
    def disconnect(self):
        if self.printer:
            try:
                self.printer.close()
            except:
                pass
            self.printer = None

    def print_invoice(self, transaction_data):
        if not self.connect():
            print("❌ Cannot connect to printer for invoice.")
            return False
            
        try:
            print("🧾 Printing invoice...")
            self.printer.set(align='center', font='b', width=2, height=2)
            self.printer.text("STRUK PARKIR\n")
            self.printer.textln(os.getenv("LABEL_UP", ""))
            self.printer.set(align='left', font='a', width=1, height=1)
            self.printer.text("-" * 32 + "\n")
            
            price = int(float(transaction_data.get('total_price', 0) or 0))
            
            self.printer.text(f"ID  : {transaction_data.get('ticket_code', '-')}\n")
            self.printer.text(f"Gate  : {transaction_data.get('device_name', '-')}\n")
            self.printer.text(f"Masuk  : {transaction_data.get('start_time', '-')}\n")
            self.printer.text(f"Keluar  : {transaction_data.get('end_time', '-')}\n")
            self.printer.text(f"Plat Nmr: {transaction_data.get('plat', '-')}\n")
            self.printer.text(f"Harga: Rp {price:,.0f}\n".replace(",", "."))

            if transaction_data.get('card_number'):
                self.printer.text(f"Kartu  : {transaction_data.get('card_number')}\n")
                self.printer.text(f"Tipe   : {transaction_data.get('card_type', '-')}\n")
                self.printer.text(f"Sisa Saldo   : {transaction_data.get('balance', '-')}\n")

            self.printer.text("-" * 32 + "\n")

            self.printer.set(align='left', font='b', width=2, height=2)
            self.printer.set(align='center', font='a', width=1, height=1)
            self.printer.textln(os.getenv("LABEL_DOWN", ""))
            self.printer.cut()
            print("✅ Invoice printed.")
            return True
        except Exception as e:
            print(f"❌ Error printing invoice: {e}")
            return False
        finally:
            self.disconnect()

    def print_qris(self, virtual_code):
        if not self.connect():
            print("❌ Cannot connect to printer for QRIS.")
            return False
            
        try:
            print("🧾 Printing QRIS...")
            self.printer.set(align='center', font='b', width=2, height=2)
            self.printer.text("QRIS PEMBAYARAN PARKIR\n")
            self.printer.textln(os.getenv("LABEL_UP", ""))
            self.printer.set(align='center', font='a', width=1, height=1)
            self.printer.text("-" * 32 + "\n")
            self.printer.qr(str(virtual_code), size=8)

            self.printer.text("-" * 32 + "\n")
            self.printer.text("Silahkan lakukan pembayaran melalui QRIS.\n")
            self.printer.text("Setelah berhasil\n Scan ulang tiket parkir anda.\n\n")

            self.printer.set(align='center', font='a', width=1, height=1)
            self.printer.textln(os.getenv("LABEL_DOWN", ""))
            self.printer.cut()
            print("✅ QRIS printed.")
            return True
        except Exception as e:
            print(f"❌ Error printing QRIS: {e}")
            return False
        finally:
            self.disconnect()
