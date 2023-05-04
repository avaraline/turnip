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

    def packet(self, addr: tuple[str, int]) -> bytes:
        return (
            bytes([self.value])
            + socket.inet_aton(addr[0])
            + struct.pack("!H", addr[1])
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
        if len(data) != 7:
            return
        cmd = Command(data[0])
        connaddr = unpack_address(data[1:])
        match cmd:
            case Command.PING:
                if addr not in self.known:
                    print("Registering {}".format(addr))
                self.known[addr] = time.time()
            case Command.REQUEST:
                if connaddr in self.known:
                    print("Requesting {} to open {}".format(connaddr, addr))
                    self.transport.sendto(Command.PUNCH.packet(addr), connaddr)
                else:
                    print("Unknown server: {}".format(connaddr))

    def expire(self, timeout):
        for addr in list(self.known.keys()):
            if (time.time() - self.known[addr]) >= timeout:
                print("Expiring {}".format(addr))
                del self.known[addr]


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
