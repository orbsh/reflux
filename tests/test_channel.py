"""The channel codec: the handshake key, framing, fragmentation, ping, close, refusal.

Tested at the byte level on a socket pair — no browser, no HTTP — because this is where a
mistake shows up as "the client silently stopped talking": a length form off by one, a mask
applied to the wrong side, a fragmented message dropped.
"""

from __future__ import annotations

import socket
import struct
import unittest

from reflux.channel import Channel, ChannelClosed, accept_key

TEXT, BINARY, CLOSE, PING, PONG, CONTINUATION = 0x1, 0x2, 0x8, 0x9, 0xA, 0x0


def client_frame(opcode: int, payload: bytes, *, final: bool = True) -> bytes:
    """A client→server frame: always masked, as the RFC requires."""
    mask = b"\x01\x02\x03\x04"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    head = bytearray([(0x80 if final else 0x00) | opcode])
    size = len(payload)
    if size < 126:
        head.append(0x80 | size)
    elif size < 65536:
        head.append(0x80 | 126)
        head += struct.pack(">H", size)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", size)
    return bytes(head) + mask + masked


def read_frame(stream) -> tuple[int, bytes]:
    """A server→client frame: never masked, so the header is the whole of it."""
    first, second = stream.read(2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack(">H", stream.read(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", stream.read(8))[0]
    return first & 0x0F, stream.read(length)


class TestHandshake(unittest.TestCase):
    def test_accept_key_matches_the_rfc_example(self) -> None:
        # RFC 6455 §1.3
        self.assertEqual(accept_key("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


class TestCodec(unittest.TestCase):
    def setUp(self) -> None:
        self.client, self.server_socket = socket.socketpair()
        self.channel = Channel(
            self.server_socket.makefile("rb"), self.server_socket.makefile("wb")
        )
        self._reader = None

    @property
    def reader(self):
        # Created only by the tests that read the server's own frames: `socket.makefile` holds
        # the fd open, so a socket "closed" while a reader exists never reaches EOF.
        if self._reader is None:
            self._reader = self.client.makefile("rb")
        return self._reader

    def tearDown(self) -> None:
        if self._reader is not None:
            self._reader.close()
        self.channel.rfile.close()
        self.channel.wfile.close()
        self.client.close()
        self.server_socket.close()

    def test_a_masked_text_frame_arrives_as_a_string(self) -> None:
        self.client.sendall(client_frame(TEXT, "你好".encode("utf-8")))
        self.assertEqual(self.channel.recv(), "你好")

    def test_a_fragmented_message_is_reassembled(self) -> None:
        self.client.sendall(client_frame(TEXT, b"Hel", final=False))
        self.client.sendall(client_frame(CONTINUATION, b"lo", final=True))
        self.assertEqual(self.channel.recv(), "Hello")

    def test_a_ping_is_answered_and_never_surfaces_as_a_message(self) -> None:
        self.client.sendall(client_frame(PING, b"beat"))
        self.client.sendall(client_frame(TEXT, b"after"))
        # recv() returns the next *message*: a ping is plumbing, answered in place
        self.assertEqual(self.channel.recv(), "after")
        self.assertEqual(read_frame(self.reader), (PONG, b"beat"))

    def test_a_close_ends_the_iteration(self) -> None:
        self.client.sendall(client_frame(CLOSE, struct.pack(">H", 1000)))
        self.assertIsNone(self.channel.recv())
        self.assertEqual(read_frame(self.reader)[0], CLOSE)

    def test_a_binary_frame_is_refused(self) -> None:
        self.client.sendall(client_frame(BINARY, b"\x00\x01"))
        with self.assertRaises(ChannelClosed):
            self.channel.recv()

    def test_both_sides_use_the_wide_length_forms(self) -> None:
        for size in (125, 126, 70000):
            with self.subTest(size=size):
                text = "x" * size
                self.client.sendall(client_frame(TEXT, text.encode("utf-8")))
                self.assertEqual(len(self.channel.recv() or ""), size)
                self.channel.send(text)
                opcode, payload = read_frame(self.reader)
                self.assertEqual((opcode, len(payload)), (TEXT, size))

    def test_a_peer_that_goes_away_raises_rather_than_hanging(self) -> None:
        self.client.shutdown(socket.SHUT_WR)  # FIN: the peer is gone, the socket is not closed
        with self.assertRaises(ChannelClosed):
            self.channel.recv()


if __name__ == "__main__":
    unittest.main()