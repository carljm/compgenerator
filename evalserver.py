"""

A simple server that accepts Python code and exec()s it.

Obviously this is unsafe. Run it only with code you trust not to
do anything malicious. This is designed to work together with
test_fuzz_comps.py.

"""
import argparse
from dataclasses import dataclass, field
import json
import re
from socket import socket, AF_INET, SOCK_STREAM
import traceback
import types
from typing import Any, Mapping


def deaddress(text: str) -> str:
    return re.sub(r"0x[0-9a-f]+", "0x...", text)


def get_ns(ns: Mapping[str, Any]) -> dict[str, Any]:
    ret = {}
    for k, v in ns.items():
        child_ns: Mapping[str, Any] | None = None
        if isinstance(v, type):
            child_ns = v.__dict__
        elif isinstance(v, types.FunctionType):
            try:
                child_ns = v()
            except Exception as e:
                child_ns = {"error": "run", "message": repr(e)}
        child: Any
        if child_ns is not None:
            child = get_ns(child_ns)
        else:
            child = deaddress(repr(v))
        ret[k] = child
    return ret


def try_exec(data: bytes) -> dict[str, Any]:
    try:
        data_str = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "UnicodeDecodeError"}
    try:
        code = compile(data_str, "<string>", "exec")
    except Exception as e:
        return {"error": "compile", "message": repr(e)}
    try:
        ns: dict[str, Any] = {}
        exec(code, ns, ns)
        del ns["__builtins__"]
    except Exception as e:
        return {"error": "run", "message": repr(e)}
    return get_ns(ns)


@dataclass
class EvalServerClient:
    port: int
    sock: socket = field(init=False)

    def __enter__(self):
        self.sock = socket()
        self.sock.connect(("localhost", self.port))
        return self

    def submit_code(self, code: str) -> dict[str, str]:
        data = code.encode("utf-8")
        data_size = len(data)
        self.sock.sendall(data_size.to_bytes(4, byteorder="big"))
        self.sock.sendall(data)
        header = self.sock.recv(4)
        output_size = int.from_bytes(header, byteorder="big")
        output = self.sock.recv(output_size)
        return json.loads(output)

    def __exit__(self, exc_type, exc_value, traceback):
        self.sock.close()


def make_server(port: int) -> socket:
    sock = socket(AF_INET, SOCK_STREAM)
    sock.bind(("localhost", port))
    sock.listen(1)
    return sock


def handle_request(sock: socket) -> None:
    header = sock.recv(4)
    data_size = int.from_bytes(header, byteorder="big")
    data = sock.recv(data_size)
    print("Got code", data)
    result = try_exec(data)
    print("Got result", result)
    output = json.dumps(result).encode("utf-8")
    output_size = len(output)
    sock.sendall(output_size.to_bytes(4, byteorder="big"))
    sock.sendall(output)


def main():
    parser = argparse.ArgumentParser("evalserver")
    parser.add_argument("-p", "--port", default=9999, type=int)
    args = parser.parse_args()

    sock = make_server(args.port)
    print("evalserver.py listening on port", args.port)
    try:
        while True:
            conn, _ = sock.accept()
            with conn:
                while True:
                    handle_request(conn)
    finally:
        sock.close()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
