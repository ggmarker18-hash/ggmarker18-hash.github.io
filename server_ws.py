#!/usr/bin/env python3
"""
Name: Leah Price
Date: 2025-10-07
Description:
  Minimal WebSocket chat server with password protection.
  - Uses asyncio + websockets
  - First message from client must be auth JSON: {"type":"auth","username":"...","password":"..."}
  - After auth, client sends {"type":"chat","text":"..."} messages.
  - Supports /users and /msg <user> <message> commands.
  - Broadcasts chat messages to all connected authenticated users with a timestamp.
"""

import asyncio
import websockets
import json
from datetime import datetime

# Server config
HOST = "0.0.0.0"
PORT = 8765
CHAT_PASSWORD = "letmein"   # <-- change this to what you want
MAX_MSG = 10_000

# Connected clients: username -> websocket
clients = {}   # username -> websocket
clients_lock = asyncio.Lock()

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

async def send_json(ws, obj):
    try:
        await ws.send(json.dumps(obj))
    except:
        pass

async def broadcast_packet(packet, exclude_username=None):
    async with clients_lock:
        for user, ws in list(clients.items()):
            if user == exclude_username:
                continue
            try:
                await send_json(ws, packet)
            except:
                # drop client on error
                del clients[user]

async def handle_command(username, text, ws):
    # Commands are forwarded from client as plain text in chat packets
    l = text.strip()
    if l == "/users":
        async with clients_lock:
            users = list(clients.keys())
        await send_json(ws, {"type":"users", "users": users})
        return True

    if l.startswith("/msg "):
        # format: /msg <user> <message>
        parts = l.split(" ", 2)
        if len(parts) < 3:
            await send_json(ws, {"type":"system", "message":"Usage: /msg <user> <message>"})
            return True
        to_user = parts[1]
        message = parts[2]
        async with clients_lock:
            target = clients.get(to_user)
        if not target:
            await send_json(ws, {"type":"system", "message":f"User '{to_user}' not found."})
            return True
        packet = {"type":"private", "from": username, "text": message, "timestamp": now_ts()}
        await send_json(target, packet)
        await send_json(ws, {"type":"system", "message":"Private message sent."})
        return True

    if l == "/quit":
        # client will close connection afterwards
        await send_json(ws, {"type":"system", "message":"Goodbye."})
        await ws.close()
        return True

    # not a special command
    return False

async def handler(ws, path):
    # Authenticate first
    try:
        auth_raw = await asyncio.wait_for(ws.recv(), timeout=15)
    except asyncio.TimeoutError:
        await send_json(ws, {"type":"auth_fail", "reason":"No auth received"})
        await ws.close()
        return
    try:
        auth = json.loads(auth_raw)
    except:
        await send_json(ws, {"type":"auth_fail", "reason":"Malformed auth"})
        await ws.close()
        return

    if auth.get("type") != "auth" or not auth.get("username") or not auth.get("password"):
        await send_json(ws, {"type":"auth_fail", "reason":"Auth required"})
        await ws.close()
        return

    username = auth["username"].strip()
    password = auth["password"]

    if password != CHAT_PASSWORD:
        await send_json(ws, {"type":"auth_fail", "reason":"Wrong password"})
        await ws.close()
        return

    # now register client
    async with clients_lock:
        if username in clients:
            await send_json(ws, {"type":"auth_fail", "reason":"Username already taken"})
            await ws.close()
            return
        clients[username] = ws

    await send_json(ws, {"type":"auth_ok"})
    # announce to others
    await broadcast_packet({"type":"system", "message":f"*** {username} joined the chat ***"}, exclude_username=username)
    # send updated users list
    async with clients_lock:
        users = list(clients.keys())
    await broadcast_packet({"type":"users", "users": users})

    try:
        async for incoming in ws:
            # expect JSON chat packets
            try:
                packet = json.loads(incoming)
            except:
                await send_json(ws, {"type":"system", "message":"Malformed packet (expecting JSON)."})
                continue

            if packet.get("type") != "chat" or "text" not in packet:
                await send_json(ws, {"type":"system", "message":"Unknown packet type."})
                continue

            text = packet["text"][:MAX_MSG]

            # check for commands
            handled = await handle_command(username, text, ws)
            if handled:
                # if command handled, optionally update user lists if needed
                async with clients_lock:
                    users = list(clients.keys())
                await broadcast_packet({"type":"users", "users": users})
                continue

            # normal broadcast
            out = {"type":"chat", "from": username, "text": text, "timestamp": now_ts()}
            await broadcast_packet(out)

    except websockets.ConnectionClosed:
        pass
    finally:
        async with clients_lock:
            if username in clients and clients[username] is ws:
                del clients[username]
        await broadcast_packet({"type":"system", "message":f"*** {username} left the chat ***"})
        async with clients_lock:
            users = list(clients.keys())
        await broadcast_packet({"type":"users", "users": users})


if __name__ == "__main__":
    print(f"Starting WebSocket chat server on ws://{HOST}:{PORT}/")
    print("Change CHAT_PASSWORD inside the script to set your room password.")

    async def main():
        async with websockets.serve(handler, HOST, PORT):
            await asyncio.Future()  # run forever

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")

