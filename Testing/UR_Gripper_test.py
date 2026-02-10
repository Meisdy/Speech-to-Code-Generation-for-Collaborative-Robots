import socket
import time

ROBOT_IP = "169.254.70.80"

# Connect to dashboard
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ROBOT_IP, 29999))

# Power on
sock.send(b"power on\n")
print(sock.recv(1024).decode())
time.sleep(2)

sock.send(b"brake release\n")
print(sock.recv(1024).decode())
time.sleep(2)

# Load a program (you need to have one saved)
sock.send(b"load /programs/test.urp\n")  # Change to your program name
print(sock.recv(1024).decode())
time.sleep(1)

# Play the program
sock.send(b"play\n")
print(sock.recv(1024).decode())
time.sleep(2)

sock.close()

# NOW send gripper commands to port 30002
print("\nSending gripper command...")
script = """
popup("Gripper test", title="Info", warning=False, error=False)
RG6(target_width=80, target_force=20, payload=0.0, set_payload=False, depth_compensation=False, slave=False)
"""

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ROBOT_IP, 30002))
sock.send(script.encode('utf-8'))
time.sleep(5)
sock.close()

print("Done!")
