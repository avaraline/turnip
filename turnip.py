#!/usr/bin/env python3

import asyncio
import enum
import os
import socket
import struct
import time

# The address and port to run on.
BIND = os.getenv("BIND", "0.0.0.0:19555")

# Expire known servers after 60 seconds without a ping by default.
TIMEOUT = int(os.getenv("TIMEOUT", 60))


class Command(enum.IntEnum):
    PING = 1
    REQUEST = 2
    PUNCH = 3

    def packet(self, addr: tuple[str, int], port: int = 0) -> bytes:
        return (
            bytes([self.value])
            + socket.inet_aton(addr[0])
            + struct.pack("!HH", addr[1], port)
        )


def unpack_address(data: bytes) -> tuple[str, int] | None:
    if len(data) != 6:
        return None
    return (socket.inet_ntoa(data[:4]), struct.unpack("!H", data[4:])[0])


class TurnipProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.known = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if len(data) != 9:
            return
        cmd = Command(data[0])
        local = unpack_address(data[1:7])
        port = struct.unpack("!H", data[7:9])[0]
        match cmd:
            case Command.PING:
                # Register this client using it's remote IP and local port. If we ever
                # decide to require a server like this, we could simply tell connecting
                # clients which port to use, instead of requiring them to know up front.
                key = (addr[0], local[1])
                # Store which port the client is using for punch packets, so we can
                # send requests back through that. Also track the last time the client
                # was seen, so we can expire them.
                self.known.setdefault(key, {}).update({addr[1]: time.time()})
            case Command.REQUEST:
                if local in self.known:
                    for punch_port in self.known[local].keys():
                        punch_addr = (local[0], punch_port)
                        open_addr = (addr[0], port)
                        print("Requesting {} to open {}".format(punch_addr, open_addr))
                        self.transport.sendto(
                            Command.PUNCH.packet(open_addr), punch_addr
                        )
                else:
                    print("Unknown client: {}".format(local))

    def expire(self, timeout):
        expired = []
        for key, ports in self.known.items():
            for port, last_seen in ports.items():
                if (time.time() - last_seen) >= timeout:
                    print("Expiring {}[{}]".format(key, port))
                    expired.append((key, port))
        for key, port in expired:
            del self.known[key][port]
            if not self.known[key]:
                del self.known[key]


async def main():
    loop = asyncio.get_running_loop()
    bind_host, bind_port = BIND.split(":")
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: TurnipProtocol(), local_addr=(bind_host, int(bind_port))
    )
    try:
        while True:
            await asyncio.sleep(5.0)
            protocol.expire(TIMEOUT)
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
