import serial
import time
serial = serial.Serial('/dev/ttyACM0', baudrate=115200, timeout=0.1)
print("Connected to rotation table")
serial.write(bytes(str(20),'utf-8'))
response = serial.read(serial.in_waiting).decode('utf-8', errors='ignore')
print("Reset to 0°")
time.sleep(1)
serial.close()
print("Disconnected from rotation table")