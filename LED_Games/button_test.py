from gpiozero import Button
from signal import pause

BUTTON_1_PIN = 23
BUTTON_2_PIN = 24

button1 = Button(BUTTON_1_PIN, pull_up=True, bounce_time=0.05)
button2 = Button(BUTTON_2_PIN, pull_up=True, bounce_time=0.05)

def button1_pressed():
    print("Button 1 pressed")

def button2_pressed():
    print("Button 2 pressed")

button1.when_pressed = button1_pressed
button2.when_pressed = button2_pressed

print("Button test started.")
print("Press Button 1 or Button 2.")
print("Press Ctrl + C to stop.")

pause()
