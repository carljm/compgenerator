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


def deaddress(text: str) -> str:
    return re.sub(r"0x[0-9a-f]+", "0x...", text)


def try_eval(data: bytes) -> dict[str, str | dict[str, str]]:
    try:
        data_str = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "UnicodeDecodeError"}
    try:
        code = compile(data_str, "<string>", "exec")
    except SyntaxError as e:
        return {"error": "SyntaxError", "message": repr(e)}
    try:
        ns = {}
        exec(code, ns, ns)
        del ns["__builtins__"]
    except Exception as e:
        return {"error": "Exception", "message": repr(e)}
    classdicts = {}
    for k, v in ns.items():
        if isinstance(v, type):
            classdict = repr(v.__dict__)
            classdicts[k] = deaddress(classdict)
    return {"result": deaddress(repr(ns)), "classdicts": classdicts}


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
    result = try_eval(data)
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
    while True:
        conn, _ = sock.accept()
        with conn:
            while True:
                handle_request(conn)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
