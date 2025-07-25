import serial
from serial.tools import list_ports

import re


def find_usb_serial_device(vid, pid, serial_number=None):
    ports = list_ports.comports()
    match_port = []

    usb_pattern = r"USB\s*VID:PID=(\w+):(\w+)\s*SER=([A-Za-z0-9]*)"

    for port in ports:
        match = re.match(usb_pattern, port.usb_info())
        if not match:
            continue

        port_vid, port_pid, port_serial = match.groups()
        if port_vid != vid or port_pid != pid:
            continue

        if serial_number and serial_number + "A" not in port[2]:
            continue

        match_port.append(port[0])

    if not match_port:
        return None
    return match_port[0] if len(match_port) == 1 else match_port


def print_all_ports():
    ports = list_ports.comports()
    for port in ports:
        print(port.usb_info())


# print(find_usb_serial_device("0403", "6001", "B0029TYY"))
