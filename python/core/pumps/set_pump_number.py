"""
set_pump_number.py
Utility to assign a pump ID to a New Era syringe pump.
Connect only ONE pump at a time when running this script.

Usage:
    python set_pump_number.py --port /dev/ttyUSB0 --number 2
    python set_pump_number.py --port COM3 --number 0
"""

import argparse
import serial


def find_current_pump_number(ser: serial.Serial, tot_range: int = 10) -> int:
    """Scan addresses and return the current pump number."""
    for i in range(tot_range):
        ser.write(str.encode('%iADR\x0D' % i))
        output = ser.readline()
        if len(output) > 0:
            print(f'Current pump number: {i}')
            return i
    print('No pump found — check cable and port.')
    return -1


def set_pump_number(ser: serial.Serial, number: int) -> None:
    """Assign a new pump ID."""
    ser.write(str.encode('*ADR%i\x0D' % number))
    ser.readline()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Assign a pump ID to a New Era syringe pump.'
    )
    parser.add_argument(
        '--port', type=str, required=True,
        help='Serial port, e.g. COM3 or /dev/ttyUSB0'
    )
    parser.add_argument(
        '--number', type=int, required=True,
        help='Pump ID to assign (0-9)'
    )
    parser.add_argument(
        '--baud', type=int, default=19200,
        help='Baud rate (default: 19200)'
    )
    args = parser.parse_args()

    if not 0 <= args.number <= 9:
        print('Error: pump number must be between 0 and 9')
        return

    ser = serial.Serial(args.port, args.baud, timeout=0.5)
    print(f'Connected to {args.port}')

    print('Before:')
    find_current_pump_number(ser)

    print(f'Setting pump number to {args.number}...')
    set_pump_number(ser, args.number)

    print('After:')
    find_current_pump_number(ser)

    ser.close()
    print('Done.')


if __name__ == '__main__':
    main()