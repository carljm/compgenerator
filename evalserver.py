"""

A simple server that accepts Python code and exec()s it.

Obviously this is unsafe. Run it only with code you trust not to
do anything malicious. This is designed to work together with
test_fuzz_comps.py.

"""
import argparse
from dataclasses import dataclass, field
import inspect
import json
import re
from socket import socket, AF_INET, SOCK_STREAM
import traceback
import types
from typing import Any, Mapping

MAX_DEPTH = 5


def deaddress(text: str) -> str:
    # repr() of some types includes the memory address
    text = re.sub(r"0x[0-9a-f]+", "0x...", text)
    # lambdas defined within listcomps lose the <listcomp> part of their qualname,
    # we don't care
    text = text.replace(".<listcomp>", "")
    return text


def exception_repr(e: Exception) -> str:
    # There is a harmless difference between 3.11 and main in these error messages.
    # See https://github.com/carljm/compgenerator/issues/4
    if isinstance(e, UnboundLocalError) and (
        match := re.fullmatch(
            r"cannot access local variable '([a-z_]+)' where it is not associated with a value",
            e.args[0],
        )
    ):
        return f"Name/UnboundLocal: {match.group(1)}"
    elif isinstance(e, NameError) and (
        match := re.fullmatch(
            r"cannot access free variable '([a-z_]+)' where it is not associated with a value in enclosing scope",
            e.args[0],
        )
    ):
        return f"Name/UnboundLocal: {match.group(1)}"
    return repr(e)


def get_ns(ns: Mapping[str, Any], depth: int) -> dict[str, Any]:
    if depth >= MAX_DEPTH:
        return {k: deaddress(repr(v)) for k, v in ns.items()}
    ret = {}
    # Make a copy because calling the inner functions may mutate
    # an outer namespace.
    for k, v in list(ns.items()):
        child_ns: Any = None
        if isinstance(v, type):
            child_ns = v.__dict__
        elif isinstance(v, types.FunctionType):
            sig = inspect.signature(v)
            # Assume all the parameters are positional
            args = [f"arg{i}" for i in range(len(sig.parameters))]
            try:
                child_ns = v(*args)
            except Exception as e:
                child_ns = {"error": "run", "message": exception_repr(e)}
        child: Any
        if child_ns is not None and isinstance(child_ns, Mapping):
            child = get_ns(child_ns, depth=depth + 1)
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
        return {"error": "compile", "message": exception_repr(e)}
    try:
        ns: dict[str, Any] = {}
        exec(code, ns, ns)
        del ns["__builtins__"]
    except Exception as e:
        return {"error": "run", "message": exception_repr(e)}
    return get_ns(ns, depth=0)


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
