import socket
import sys
import time

TIMEOUT = 10
WATCHDOG_PORT = 3000


def open_watchdog_socket(ip):
    """
    Description: Opens a TCP socket for the watchdog functionality.
    Input: ip - A string representing the IP address.
    Output: None (prints messages to the console).
    """

    # Create TCP socket for watchdog
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allowing using a used port
    except socket.error:
        print("Error creating socket.")
        return

    sock.bind(('localhost', WATCHDOG_PORT))
    sock.listen(1)

    print("*****Watchdog: listening on port 3000...*****")

    while True:
        # Accept incoming connection
        betterping_socket, addr = sock.accept()
        print("Watchdog connected to betterping program")

        start_time = time.time()

        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= TIMEOUT:
                break
            try:
                got_reply = betterping_socket.recv(1024)
                # Check if got pong update
                if got_reply == b"got_reply":
                    start_time = time.time()
                if got_reply == b"stopped by ctrl-c":
                    print("Close watchdog")
                    sock.close()
                    betterping_socket.close()

                    sys.exit(1)

            except socket.error:
                print("Error in watchdog socket receiving data")

        print(f"server {ip} cannot be reached.")
        print("Watchdog timeout (10 seconds). Close sockets and END.")
        sock.close()
        betterping_socket.close()

        sys.exit(1)




