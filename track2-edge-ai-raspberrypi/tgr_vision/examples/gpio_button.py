# TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE
# ต่อปุ่มที่ GPIO17 (ขา 11) กับ GND (ขา 9), LED ที่ GPIO27 (ขา 13) ผ่าน R 330 โอห์ม
from gpiozero import Button, LED
from signal import pause

btn = Button(17)        # ใช้ pull-up ภายในชิป ไม่ต้องต่อตัวต้านทานเพิ่ม
led = LED(27)
btn.when_pressed = lambda: (led.on(), print('กดปุ่ม: ถ่ายภาพ'))
btn.when_released = led.off
pause()
