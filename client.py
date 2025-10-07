"""
Name: Leah Price
Date: 10/7/2025
Descirption: Client file for the tcp chat
"""

import socket
import threading
import sys

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5555

def listen(sock):
    """Listen for messages from the server."""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print("Disconnected from server.")
                break
            print("\n" + data.decode("UTF-8"))
        except:
            break

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, SERVER_PORT))

    prompt = s.recv(1024).decode("UTF-8")
    print(prompt, end="")
    username = input()
    s.sendall(username.encode("UTF-8"))

    threading.Thread(target=listen, args=(s,), daemon=True).start()

    print("Commands: /users  /msg <user> <message>  /delay <seconds> <message>  /quit")
    while True:
        try:
            msg = input()
        except EOFError:
            break
        if not msg:
            continue
        s.sendall(msg.encode("UTF-8"))
        if msg.lower() == "/quit":
            break

    s.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)