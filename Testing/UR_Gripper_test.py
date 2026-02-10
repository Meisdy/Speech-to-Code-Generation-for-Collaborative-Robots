import socket
import time

ROBOT_IP = "169.254.70.80"

print("Starting gripper test...")

try:
    print("Opening new connection...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ROBOT_IP, 29999))
    sock.recv(1024)

    print("Loading program to open Gripper...")
    sock.send(b"load /programs/open_UG2_Gripper.urp\n")
    response = sock.recv(1024).decode()
    print(f"Load response: {response}")
    print("Playing program...")
    sock.send(b"play\n")
    response = sock.recv(1024).decode()
    print(f"Play response: {response}")

    time.sleep(3)

    print("Loading program to Close Gripper...")
    sock.send(b"load /programs/close_UG2_Gripper.urp\n")
    response = sock.recv(1024).decode()
    print(f"Load response: {response}")
    print("Playing program...")
    sock.send(b"play\n")
    response = sock.recv(1024).decode()
    print(f"Play response: {response}")

    sock.close()
    print("Done!")

except Exception as e:
    print(f"ERROR: {e}")
