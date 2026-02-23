import socket
import struct

HOST = "192.168.1.100"  # robot IP
PORT = 30003           # real-time interface

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

data = s.recv(1108)  # typical packet size

# First 4 bytes = message length
msg_size = struct.unpack('!i', data[0:4])[0]

# Unpack all doubles after header
doubles = struct.unpack('!{}d'.format((len(data)-4)//8), data[4:])

# Joint positions (example indices)
joint_positions = doubles[32:38]

# TCP pose
tcp_pose = doubles[56:62]

print("Joints:", joint_positions)
print("TCP:", tcp_pose)

s.close()