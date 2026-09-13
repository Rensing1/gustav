"""Emit a labelled, monochrome PNG for the real print-upload acceptance test."""

import sys
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

image = Image.new("RGB", (1400, 650), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype("DejaVuSans.ttf", 42)
small = ImageFont.truetype("DejaVuSans.ttf", 34)
for x, heading, detail in [(35, "Eingabe", "Sensor"), (520, "Verarbeitung", "Programm"), (1005, "Ausgabe", "Anzeige")]:
    draw.rectangle((x, 140, x + 360, 405), outline="black", width=4)
    draw.text((x + 180, 215), heading, font=font, fill="black", anchor="mm")
    draw.text((x + 180, 325), detail, font=small, fill="black", anchor="mm")
for x in [410, 895]:
    draw.line((x, 270, x + 90, 270), fill="black", width=4)
    draw.line((x + 70, 253, x + 90, 270, x + 70, 287), fill="black", width=4)
draw.text((700, 535), "Temperatur messen, prüfen und darstellen", font=font, fill="black", anchor="mm")
stream = BytesIO()
image.save(stream, format="PNG")
sys.stdout.buffer.write(stream.getvalue())
