import socket, base64, json

AES_KEY = bytes.fromhex("2B7E151628AED2A6ABF7158809CF4F3C")
AES_IV  = bytes.fromhex("000102030405060708090A0B0C0D0E0F")

from Crypto.Cipher import AES

def encrypt(plaintext):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + chr(pad_len) * pad_len
    enc = cipher.encrypt(padded.encode())
    return base64.b64encode(enc).decode()

data = {"movement_class": 0, "timestamp": 1761897753.3597476}
payload = json.dumps(data)

encrypted = encrypt(payload) + "\n"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("172.20.10.5", 4210))   # 👈 Replace with ESP32 IP shown in Serial Monitor
sock.sendall(encrypted.encode())
print("Sent:", payload)
