import socket
import time

ROBOT_IP = "169.254.70.80"


def send_command(sock, cmd: str) -> str:
    sock.send(cmd.encode())
    return sock.recv(1024).decode().strip()


def wait_for_program_start(sock) -> None:
    """Wait until program actually starts playing"""
    while True:
        response = send_command(sock, "programState\n")
        if "PLAYING" in response:
            return
        time.sleep(0.05)


def wait_for_program_finish(sock) -> None:
    """Wait until program stops"""
    while True:
        response = send_command(sock, "programState\n")
        if "STOPPED" in response:
            return
        time.sleep(0.1)


print("Starting gripper test...")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ROBOT_IP, 29999))
    sock.recv(1024)

    # OPEN
    print("1. OPEN Gripper")
    send_command(sock, "load /programs/open_UG2_Gripper.urp\n")
    send_command(sock, "play\n")
    wait_for_program_start(sock)
    wait_for_program_finish(sock)
    print("  Done")

    # CLOSE
    print("2. CLOSE Gripper")
    send_command(sock, "load /programs/close_UG2_Gripper.urp\n")
    send_command(sock, "play\n")
    wait_for_program_start(sock)
    wait_for_program_finish(sock)
    print("  Done")

    sock.close()
    print("\nComplete!")

except Exception as e:
    print(f"ERROR: {e}")
