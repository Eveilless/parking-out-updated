import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont
import logging

# Global variables for OLED elements
disp = None
draw = None
image = None
font = None
widthOled = 128
heightOled = 64
line1 = 0
line2 = 10
line3 = 20
line4 = 30


def setup_oled():
    global disp, draw, image, font

    try:
        # Initialize display (I2C)
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=None)
        disp.begin()
        disp.clear()
        disp.display()

        # Create blank image and drawing object
        image = Image.new('1', (disp.width, disp.height))
        draw = ImageDraw.Draw(image)

        # Load default font
        font = ImageFont.load_default()

        logging.info("OLED display initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize OLED display: {e}")


def print_oled(str1="", str2="", str3="", str4=""):
    global disp, draw, image, font
    
    try:
        if not all([disp, draw, image, font]):
            logging.warning("OLED not initialized. Call setup_oled() first.")
            return

        # Clear the image canvas
        draw.rectangle((0, 0, widthOled, heightOled), outline=0, fill=0)

        # Draw text lines
        draw.text((0, line1), str1, font=font, fill=255)
        draw.text((0, line2), str2, font=font, fill=255)
        draw.text((0, line3), str3, font=font, fill=255)
        draw.text((0, line4), str4, font=font, fill=255)

        # Send image to OLED display
        disp.image(image)
        disp.display()
    except Exception as e:
        print(e)
