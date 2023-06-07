import threading
import select
import os
import socket
import struct
import sys
import time
from watchdog import open_watchdog_socket

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
TIMEOUT = 1
WATCHDOG_ADDR = ('localhost', 3000)


# Checksum algo
def calculate_checksum(packet):
    """
    Description: Calculates the checksum of the given packet using an algorithm.
    We cast the C version from Moodle to Python
    Input: packet - A byte string representing the packet.
    Output: The calculated checksum value.
    """
    # Calculate the checksum of the given packet
    countTo = (len(packet) // 2) * 2
    sum = 0

    for i in range(0, countTo, 2):
        sum += (packet[i] << 8) + packet[i + 1]
    if countTo < len(packet):
        sum += packet[len(packet) - 1] << 8

    sum = (sum >> 16) + (sum & 0xFFFF)
    sum += (sum >> 16)
    result = ~sum & 0xFFFF
    return result


def create_packet(seq_num):
    """
    Description: Creates an ICMP packet.
    Input: seq_num - An integer representing the sequence number of the packet.
    Output: A byte string and header representing the ICMP packet.
    """
    # ICMP packet with a dummy header with random checksum value - 0.
    checksum_value = 0
    header = struct.pack("BBHHH", ICMP_ECHO_REQUEST, 0, checksum_value, os.getpid(), seq_num)
    data = b"Data"

    # Updating header with real checksum.
    checksum_value = calculate_checksum(header + data)
    header = struct.pack("BBHHH", ICMP_ECHO_REQUEST, 0, socket.htons(checksum_value), os.getpid(), seq_num)

    return header + data


def receive_ping(sock, seq_num):
    """
    Description: Receives a ping reply from the socket and processes it.
    Input:
        sock - The socket to receive the reply on.
        seq_num - An integer representing the expected sequence number of the reply.
    Output: A string containing information about the received ping reply or None if no reply is received.
    """
    # Receive ping reply from the socket
    start_time = time.time()
    elapsed_time = time.time() - start_time
    ready = select.select([sock], [], [], TIMEOUT - elapsed_time)
    if ready[0]:
        packet, addr = sock.recvfrom(1024)
        icmp_header = packet[20:28]
        rtype, code, checksum, p_id, rseq_num = struct.unpack("BBHHH", icmp_header)
        if rtype == ICMP_ECHO_REPLY and rseq_num == seq_num:
            # Return a string with all data in the format we asked.
            return f'{len(packet)} bytes from {addr[0]} icmp_seq={rseq_num} ttl={packet[8]}' \
                f' time={(time.time() - start_time) * 1000:.3f} ms'
        elif rtype == 3:
            print(f"Destination {ip} is unreachable")
            return

    return None


def send_ping(sock, dest_addr, seq_num):
    """
    Description: Sends an ICMP Echo Request packet to the specified destination address and waits for a reply.
    Input:
        sock - The socket to use for sending the packet.
        dest_addr - A string representing the destination IP address.
        seq_num - An integer representing the sequence number of the packet.
    """
    packet = create_packet(seq_num)
    sock.sendto(packet, (dest_addr, 1))

    return receive_ping(sock, seq_num)


def ping(ip, watchdog_socket, watchdog_thread):
    """
    Description: Performs ICMP ping to the specified IP address.
    Input: ip - A string representing the IP address to ping.
    Output: None (prints the ping results to the console).
    """
    try:
        dest_addr = socket.gethostbyname(ip)
    except socket.gaierror:
        print("Could not resolve hostname:", ip)
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except socket.error:
        print("Error creating socket.")
        return

    seq_num = 1
    first_flag = True

    try:
        # Continue pinging only if watchdog_thread is alive.
        while watchdog_thread.is_alive():
            if first_flag:
                print(f"PING {dest_addr}")
                first_flag = False
            try:
                answer = send_ping(sock, dest_addr, seq_num)
                if answer:
                    # Notify watchdog
                    watchdog_socket.send(b"got_reply")
                    print(answer)
                else:
                    # Notify watchdog
                    watchdog_socket.send(b"did not got answer")
                    print("Request timed out.")
            except socket.error:
                print("Error sending/receiving data.")
                sock.close()
                sys.exit(1)

            seq_num += 1
            time.sleep(2)
    except KeyboardInterrupt:
        print('Ping stopped by Ctrl-c')
        # Notify watchdog
        watchdog_socket.send(b"stopped by ctrl-c")
    finally:
        watchdog_socket.close()
        sock.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python myping.py <addr>")
        sys.exit(1)

    ip = sys.argv[1]
    # Create thread for watchdog and execute it
    watchdog_thread = threading.Thread(target=open_watchdog_socket, args=(ip,))
    watchdog_thread.start()

    # Creating a TCP socket to connect the watchdog's socket
    try:
        watchdog_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        watchdog_socket.connect(WATCHDOG_ADDR)
        print("Betterping connected to watchdog")

        ping(ip, watchdog_socket, watchdog_thread)
    except socket.error:
        print("Error raised while creating/ using socket.")
        if watchdog_socket:  # The error occurred after initialize the socket.
            watchdog_socket.close()
        sys.exit(1)


