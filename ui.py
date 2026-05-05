import sys
import os
import requests  # For downloading images from URLs
from PyQt5.QtWidgets import QApplication, QWidget, QShortcut
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QPolygon, QFontMetrics, QKeySequence
from PyQt5.QtCore import Qt, QTimer, QDateTime, QPoint, pyqtSignal, QObject, QThread, pyqtSlot

# === Configuration Constants === #
APP_TITLE = "Parking System TAZAKA"
LOGO_FILENAME = "assets/logo-tzk.png"
BACKGROUND_FILENAME = "assets/background.png"  # rasio 16:9 960x540
CONTENT_FILENAME = "assets/content.png"
HEADER_BG_COLOR = "#FFFFFF"
HEADER_TEXT_COLOR = "#000000"
FOOTER_BG_COLOR = "#FFFFFF"
FOOTER_TEXT_COLOR = "#000000"
CONTENT_BG_COLOR = "#f0f0f0"
SHADOW_COLOR = "#000000"
TEXT_COLOR = "#FFFFFF"
DEFAULT_FONT = QFont("Arial", 36, QFont.Bold)
HEADER_FONT = QFont("Arial", 20, QFont.Bold)
FOOTER_FONT = QFont("Arial", 28, QFont.Bold)

# Layout proportions
HEADER_HEIGHT_RATIO = 0.05  # 5% of screen height
FOOTER_HEIGHT_RATIO = 0.10  # 10% of screen height
CONTENT_HEIGHT_RATIO = 0.85  # 85% of screen height

# === Signal Handler === #


class SignalHandler(QObject):
    welcome_text_changed = pyqtSignal(str)


# === Image Downloader for URL Support === #


class ImageDownloader(QObject):
    image_downloaded = pyqtSignal(bytes, str)  # image_data, image_type
    download_failed = pyqtSignal(str, str)     # error_message, image_type

    @pyqtSlot(str, str)
    def download_image(self, url, image_type):
        """Download image from URL. image_type can be 'vehicle' or 'second'"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            self.image_downloaded.emit(response.content, image_type)
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {image_type} image: {e}")
            self.download_failed.emit(str(e), image_type)


# === Global Vars === #
main_widget = None
signal_handler = SignalHandler()
app = None

# === Main Custom UI Widget === #


class CustomWidget(QWidget):
    # Signals for starting image downloads
    start_vehicle_download = pyqtSignal(str, str)  # url, image_type
    start_second_download = pyqtSignal(str, str)   # url, image_type

    def __init__(self, mode="welcome"):
        super().__init__()
        self.mode = mode
        self.setWindowTitle(APP_TITLE)
        self.resize(1080, 720)
        self.font = DEFAULT_FONT
        self.logo = self.load_logo()
        self.background_image = self.load_background()
        self.content_image = self.load_content()

        # Get welcome text from environment or use default
        self.welcome_text = os.getenv(
            "WELCOME_TEXT", "SELAMAT DATANG DI UNIGUARD PARKING SYSTEM").upper()
        self.payment_instruction_text = "Please tap your eMoney card"

        self.setup_signals()
        self.setup_timer()
        self.setup_shortcuts()
        self.setup_image_downloader()  # Setup image downloading thread
        self.showFullScreen()

        self.payment_data = {}
        self.vehicle_image = QPixmap()
        self.second_image = QPixmap()  # Added for second image in payment mode

    def set_payment_data(self, data_dict):
        self.payment_data.update(data_dict)
        self.update()

    def set_vehicle_image(self, url_or_path):
        """Set vehicle image from URL or local file path"""
        if not url_or_path:
            self.vehicle_image = QPixmap()
            self.update()
            return

        if url_or_path.startswith('http://') or url_or_path.startswith('https://'):
            print(f"Requesting download for vehicle image: {url_or_path}")
            self.start_vehicle_download.emit(url_or_path, "vehicle")
            # Keep current image while loading
        elif os.path.exists(url_or_path):
            self.vehicle_image = QPixmap(url_or_path)
            self.update()
        else:
            print(f"Vehicle image path not found: {url_or_path}")
            self.vehicle_image = QPixmap()
            self.update()

    def set_second_image(self, url_or_path):
        """Set second image from URL or local file path"""
        if not url_or_path:
            self.second_image = QPixmap()
            self.update()
            return

        if url_or_path.startswith('http://') or url_or_path.startswith('https://'):
            print(f"Requesting download for second image: {url_or_path}")
            self.start_second_download.emit(url_or_path, "second")
            # Keep current image while loading
        elif os.path.exists(url_or_path):
            self.second_image = QPixmap(url_or_path)
            self.update()
        else:
            print(f"Second image path not found: {url_or_path}")
            self.second_image = QPixmap()
            self.update()

    def set_content_image(self, image_path):
        """Dynamically set content image from file path"""
        if os.path.exists(image_path):
            self.content_image = QPixmap(image_path)
            print(f"Content image loaded: {image_path}")
        else:
            self.content_image = QPixmap()
            print(f"Content image not found: {image_path}")
        self.update()

    def set_content_pixmap(self, pixmap):
        """Dynamically set content image from QPixmap object"""
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.content_image = pixmap
            print("Content image set from pixmap")
        else:
            self.content_image = QPixmap()
            print("Invalid pixmap provided")
        self.update()

    def clear_content(self):
        """Clear the content image"""
        self.content_image = QPixmap()
        print("Content image cleared")
        self.update()

    def load_logo(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, LOGO_FILENAME)
        return QPixmap(logo_path)

    def load_background(self):
        # Try to get background filename from environment variable
        bg_filename = os.getenv("BACKGROUND_IMAGE", BACKGROUND_FILENAME)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        background_path = os.path.join(script_dir, "assets", bg_filename)
        return QPixmap(background_path)

    def load_content(self):
        # Try to get content filename from environment variable
        content_filename = os.getenv("CONTENT_FILENAME", CONTENT_FILENAME)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        content_path = os.path.join(script_dir, content_filename)
        return QPixmap(content_path)

    def setup_signals(self):
        signal_handler.welcome_text_changed.connect(self.set_welcome_text)

    def setup_image_downloader(self):
        """Setup image downloader thread for URL support"""
        self.image_thread = QThread()
        self.image_downloader = ImageDownloader()
        self.image_downloader.moveToThread(self.image_thread)

        # Connect signals
        self.start_vehicle_download.connect(
            self.image_downloader.download_image)
        self.start_second_download.connect(
            self.image_downloader.download_image)
        self.image_downloader.image_downloaded.connect(self.on_image_ready)
        self.image_downloader.download_failed.connect(self.on_image_fail)

        self.image_thread.start()

    @pyqtSlot(bytes, str)
    def on_image_ready(self, image_data, image_type):
        """Handle successful image download"""
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        if image_type == "vehicle":
            self.vehicle_image = pixmap
            print("Vehicle image loaded successfully from URL.")
        elif image_type == "second":
            self.second_image = pixmap
            print("Second image loaded successfully from URL.")

        self.update()

    @pyqtSlot(str, str)
    def on_image_fail(self, error_message, image_type):
        """Handle failed image download"""
        print(f"Failed to load {image_type} image from URL: {error_message}")

        if image_type == "vehicle":
            self.vehicle_image = QPixmap()
        elif image_type == "second":
            self.second_image = QPixmap()

        self.update()

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F11"), self).activated.connect(
            self.toggle_fullscreen)

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def set_welcome_text(self, new_text):
        self.welcome_text = new_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.mode == "welcome":
            self.draw_three_section_layout(painter)
        elif self.mode == "payment":
            self.draw_three_section_payment_layout(painter)

    def draw_three_section_layout(self, painter):
        w, h = self.width(), self.height()

        # Calculate section heights
        header_height = int(h * HEADER_HEIGHT_RATIO)
        footer_height = int(h * FOOTER_HEIGHT_RATIO)
        content_height = h - header_height - footer_height

        # Draw header section (top 5%)
        self.draw_header_section(painter, 0, 0, w, header_height)

        # Draw content section (middle 85%)
        self.draw_content_section(painter, 0, header_height, w, content_height)

        # Draw footer section (bottom 10%)
        self.draw_footer_section(
            painter, 0, header_height + content_height, w, footer_height)

    def draw_header_section(self, painter, x, y, width, height):
        # Draw header background
        painter.fillRect(x, y, width, height, QColor(HEADER_BG_COLOR))

        # Get current date and time
        now = QDateTime.currentDateTime()
        painter.setPen(QColor(HEADER_TEXT_COLOR))
        painter.setFont(HEADER_FONT)

        # Format date and time separately
        date_text = now.toString("dddd, dd MMMM yyyy")
        time_text = now.toString("hh:mm:ss")

        # Draw date in the left corner (x=30 as per specifications)
        date_rect = painter.viewport()
        date_rect.setX(x + 30)  # 30px margin from left as per specification
        date_rect.setY(y)
        date_rect.setWidth(width // 2 - 30)  # Left half minus margin
        date_rect.setHeight(height)

        painter.drawText(date_rect, Qt.AlignLeft | Qt.AlignVCenter, date_text)

        # Draw time in the right corner
        time_rect = painter.viewport()
        time_rect.setX(x + width // 2)
        time_rect.setY(y)
        time_rect.setWidth(width // 2 - 30)  # Right half minus margin
        time_rect.setHeight(height)

        painter.drawText(time_rect, Qt.AlignRight | Qt.AlignVCenter, time_text)

    def draw_content_section(self, painter, x, y, width, height):
        # Draw background image if available, otherwise use solid color
        if not self.background_image.isNull():
            # Scale the background image to fit exactly within the content area
            scaled_bg = self.background_image.scaled(
                width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Center the background image in the content area
            bg_x = x + (width - scaled_bg.width()) // 2
            bg_y = y + (height - scaled_bg.height()) // 2

            # Ensure background image stays within content section boundaries
            bg_x = max(x, min(bg_x, x + width - scaled_bg.width()))
            bg_y = max(y, min(bg_y, y + height - scaled_bg.height()))

            # Clip the drawing area to prevent overflow into header/footer
            painter.save()
            painter.setClipRect(x, y, width, height)
            painter.drawPixmap(bg_x, bg_y, scaled_bg)
            painter.restore()
        else:
            # Fallback to solid color background
            painter.fillRect(x, y, width, height, QColor(CONTENT_BG_COLOR))

        # Draw content image if available (overlaid on background)
        if not self.content_image.isNull():
            # Scale the content image to fit the area while maintaining aspect ratio
            # Add margins to ensure image doesn't touch boundaries
            margin = 20
            scaled_content = self.content_image.scaled(
                width - (margin * 2), height - (margin * 2), Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Center the image in the content area with margins
            img_x = x + (width - scaled_content.width()) // 2
            img_y = y + (height - scaled_content.height()) // 2

            # Ensure the image stays within the content section boundaries
            img_x = max(x + margin, min(img_x, x + width -
                        scaled_content.width() - margin))
            img_y = max(y + margin, min(img_y, y + height -
                        scaled_content.height() - margin))

            painter.drawPixmap(img_x, img_y, scaled_content)

    def draw_footer_section(self, painter, x, y, width, height):
        # Draw footer background
        painter.fillRect(x, y, width, height, QColor(FOOTER_BG_COLOR))

        # Draw welcome text
        painter.setPen(QColor(FOOTER_TEXT_COLOR))
        painter.setFont(FOOTER_FONT)

        # Center the welcome text in footer
        painter.drawText(x, y, width, height,
                         Qt.AlignCenter, self.welcome_text)

    def draw_three_section_payment_layout(self, painter):
        w, h = self.width(), self.height()

        # Calculate section heights (same as welcome mode)
        header_height = int(h * HEADER_HEIGHT_RATIO)
        footer_height = int(h * FOOTER_HEIGHT_RATIO)
        content_height = h - header_height - footer_height

        # Draw header section (same as welcome)
        self.draw_header_section(painter, 0, 0, w, header_height)

        # Draw payment content section (white background with payment data)
        self.draw_payment_content_section(
            painter, 0, header_height, w, content_height)

        # Draw footer section (same as welcome)
        self.draw_footer_section(
            painter, 0, header_height + content_height, w, footer_height)

    def draw_payment_content_section(self, painter, x, y, width, height):
        # Draw white background for payment content
        painter.fillRect(x, y, width, height, QColor("#FFFFFF"))

        # Calculate layout areas
        left_width = int(width * 0.6)  # 60% for payment data
        right_width = width - left_width  # 40% for vehicle photo
        margin = 20

        # Draw payment data on the left side
        self.draw_payment_data(painter, x + margin, y + margin,
                               left_width - margin * 2, height - margin * 2)

        # Draw vehicle photo on the right side
        self.draw_vehicle_photo(painter, x + left_width + margin, y + margin,
                                right_width - margin * 2, height - margin * 2)

    def draw_payment_data(self, painter, x, y, width, height):
        # Set font for payment data
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.setPen(QColor("#333333"))  # Dark gray text

        # Calculate total content height for vertical centering
        title_height = 30
        line_spacing = 45  # Increased from 35 to 45 for better readability
        data_lines = len(self.payment_data)
        total_content_height = title_height + 30 + (data_lines * line_spacing)

        # Calculate starting Y position for vertical centering
        start_y = y + (height - total_content_height) // 2
        current_y = start_y

        # Draw title
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.setPen(QColor("#000000"))  # Black text for title
        painter.drawText(x, current_y, "DATA TIKET PARKIR")
        current_y += title_height + 30  # Increased spacing after title

        # Draw payment data
        painter.setFont(QFont("Arial", 18, QFont.Normal))
        painter.setPen(QColor("#333333"))  # Dark gray text

        for key, value in self.payment_data.items():
            line = f"{key}: {value}"
            painter.drawText(x, current_y, line)
            current_y += line_spacing

    def draw_vehicle_photo(self, painter, x, y, width, height):
        # Calculate area for two images (stacked vertically)
        image_height = (height - 60) // 2  # Subtract margin and divide by 2
        margin_between = 20

        # Draw first image (top half)
        first_img_y = y
        if not self.vehicle_image.isNull():
            # Scale the first image to fit the area
            scaled_vehicle = self.vehicle_image.scaled(
                width, image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Center the image in the area
            img_x = x + (width - scaled_vehicle.width()) // 2
            img_y = first_img_y + (image_height - scaled_vehicle.height()) // 2

            # Ensure image stays within bounds
            img_x = max(x, min(img_x, x + width - scaled_vehicle.width()))
            img_y = max(first_img_y, min(img_y, first_img_y +
                        image_height - scaled_vehicle.height()))

            painter.drawPixmap(img_x, img_y, scaled_vehicle)
        else:
            # Draw placeholder for first image
            painter.setPen(QColor("#CCCCCC"))
            painter.drawRect(x, first_img_y, width, image_height)

            painter.setPen(QColor("#666666"))
            painter.setFont(QFont("Arial", 14, QFont.Normal))
            placeholder_text = "FOTO KENDARAAN 1\nTIDAK TERSEDIA"
            painter.drawText(x, first_img_y, width, image_height,
                             Qt.AlignCenter, placeholder_text)

        # Draw second image (bottom half)
        second_img_y = y + image_height + margin_between
        if not self.second_image.isNull():
            # Scale the second image to fit the area
            scaled_second = self.second_image.scaled(
                width, image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Center the image in the area
            img_x = x + (width - scaled_second.width()) // 2
            img_y = second_img_y + (image_height - scaled_second.height()) // 2

            # Ensure image stays within bounds
            img_x = max(x, min(img_x, x + width - scaled_second.width()))
            img_y = max(second_img_y, min(img_y, second_img_y +
                        image_height - scaled_second.height()))

            painter.drawPixmap(img_x, img_y, scaled_second)
        else:
            # Draw placeholder for second image
            painter.setPen(QColor("#CCCCCC"))
            painter.drawRect(x, second_img_y, width, image_height)

            painter.setPen(QColor("#666666"))
            painter.setFont(QFont("Arial", 14, QFont.Normal))
            placeholder_text = "FOTO KENDARAAN 2\nTIDAK TERSEDIA"
            painter.drawText(x, second_img_y, width, image_height,
                             Qt.AlignCenter, placeholder_text)

    def reset_to_welcome(self):
        """Membersihkan semua data pembayaran dan mengembalikan UI ke mode welcome."""
        print("🔄 Mereset UI ke mode welcome dan membersihkan data...")

        # Kosongkan dictionary data pembayaran
        self.payment_data.clear()

        # Reset gambar ke pixmap kosong
        self.vehicle_image = QPixmap()
        self.second_image = QPixmap()

        # Kembalikan mode ke welcome
        self.mode = "welcome"

        # Atur ulang teks footer ke default
        default_welcome_text = os.getenv(
            "WELCOME_TEXT", "SELAMAT DATANG DI TAZAKA PARKING SYSTEM").upper()
        self.set_welcome_text(default_welcome_text)

        # Paksa UI untuk menggambar ulang
        self.update()

# === Public API === #


def show_ui():
    global main_widget, app
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    main_widget = CustomWidget()
    main_widget.setCursor(Qt.BlankCursor)
    main_widget.show()
    return main_widget


def show_ui_payment(ticket_data):
    global main_widget, app
    app = QApplication(sys.argv)
    main_widget = CustomWidget(mode="payment")
    main_widget.setCursor(Qt.BlankCursor)
    main_widget.set_payment_data(ticket_data)
    main_widget.show()
    return main_widget


def set_welcome_text(text):
    if app and app.thread() == QThread.currentThread() and main_widget:
        main_widget.set_welcome_text(text)
    else:
        signal_handler.welcome_text_changed.emit(text)


def set_content_image(image_path):
    """Dynamically set content image from external modules"""
    if app and app.thread() == QThread.currentThread() and main_widget:
        main_widget.set_content_image(image_path)


def set_content_pixmap(pixmap):
    """Dynamically set content image from QPixmap object"""
    if app and app.thread() == QThread.currentThread() and main_widget:
        main_widget.set_content_pixmap(pixmap)


def clear_content():
    """Clear the content image"""
    if app and app.thread() == QThread.currentThread() and main_widget:
        main_widget.clear_content()


def set_second_image(image_path):
    """Set the second image for payment mode"""
    if app and app.thread() == QThread.currentThread() and main_widget:
        main_widget.set_second_image(image_path)


def switch_to_welcome_mode():
    """Membersihkan data pembayaran dan mengembalikan UI ke mode welcome."""
    if main_widget:
        main_widget.reset_to_welcome()


# === Main Entry === #
if __name__ == "__main__":
    show_ui()
    app.exec_()
