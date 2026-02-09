import socket
import time

ROBOT_IP = "169.254.70.80"  # e.g., UR5e
port = 30002

# Test script
script = """
def test_gripper():
    rg_grip(110, 20)  # Open
    sleep(2)
    rg_grip(50, 40)   # Close
    sleep(2)
    rg_grip(110, 20)  # Open again
end
test_gripper()
"""

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ROBOT_IP, port))
sock.send(script.encode())
sock.close()
