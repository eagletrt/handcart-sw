a = 0b00000001
b = 0b00000000

c = bytearray(b'.\x01\x00')
d = bytearray.fromhex('0100')
print(d.hex())
