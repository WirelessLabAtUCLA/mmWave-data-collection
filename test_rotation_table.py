#!/usr/bin/env python3
"""Test script for rotation table Arduino communication"""
import serial
import time
import sys

def test_rotation_table(port='/dev/ttyACM0', baudrate=115200):
    """Test the rotation table with various commands"""
    
    print(f"Opening serial port {port} at {baudrate} baud...")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"✓ Serial port opened successfully")
        
        # Wait for Arduino to reset (DTR triggers reset on most Arduinos)
        print("Waiting 2 seconds for Arduino to initialize...")
        time.sleep(2)
        
        # Clear any startup messages
        if ser.in_waiting:
            startup_msg = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            print(f"Arduino startup message: {startup_msg}")
        
        # Test various command formats
        test_angles = [0, 10, -10, 20, 0]
        
        for angle in test_angles:
            print(f"\n--- Testing angle: {angle}° ---")
            
            # Try command without newline
            print(f"Sending: '{angle}'")
            ser.write(bytes(str(angle), 'utf-8'))
            time.sleep(0.5)
            
            # Check for response
            if ser.in_waiting:
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                print(f"Response: {response}")
            else:
                print("No response received")
            
            # Try with newline
            print(f"Sending: '{angle}\\n'")
            ser.write(bytes(str(angle) + '\n', 'utf-8'))
            time.sleep(0.5)
            
            # Check for response
            if ser.in_waiting:
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                print(f"Response: {response}")
            else:
                print("No response received")
            
            print(f"Waiting 3 seconds for rotation...")
            time.sleep(3)
        
        # Reset to zero
        print("\n--- Resetting to 0° ---")
        ser.write(bytes('0\n', 'utf-8'))
        time.sleep(2)
        
        ser.close()
        print("\n✓ Test complete!")
        
    except serial.SerialException as e:
        print(f"✗ Serial port error: {e}")
        print("\nTroubleshooting:")
        print("1. Check if you're in the 'dialout' group: groups")
        print("2. Add yourself if needed: sudo usermod -a -G dialout $USER")
        print("3. Log out and back in after adding to group")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        ser.close()
        sys.exit(0)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = '/dev/ttyACM0'
    
    print("=== Rotation Table Test ===\n")
    test_rotation_table(port)

