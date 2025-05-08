#!/usr/bin/env python3
"""
Start a vllm server as a subprocess and listen to an exit command
on a separate port. When exit is received, shut down the server
and listening thread and exit. The exit command is in the format
'exit:KEY'.
"""

import argparse
import logging
import threading
import socket
import subprocess
import sys
import os
import time
import secrets
from typing import Optional, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y%m%d %H:%M:%S",
)
log = logging.getLogger("llm_client_server.server")


class EnvDefault(argparse.Action):
    def __init__(
        self, envvar: str, required: bool = True, default: Any = None, **kwargs
    ):
        if envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


def start_server_process(model: str, port: int, key: str) -> subprocess.Popen:
    """Start the server as a subprocess and redirect output to stdout."""

    server_process = subprocess.Popen(
        ["vllm", "serve", f"--port={port}", f"--api-key={key}", model],
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )
    return server_process


def command_listener(
    server_process: subprocess.Popen, port: int, secret_key: str
) -> None:
    """Listen for commands on port with API key authentication."""
    server_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(1)

    try:
        while not shutdown_event.is_set():
            # Set a timeout so we can check the shutdown_event periodically
            server_socket.settimeout(1.0)
            try:
                # accept blocks until a client connects
                client_socket, client_address = server_socket.accept()
                client_socket.settimeout(1.0)

                data: str = client_socket.recv(1024).decode("utf-8").strip()
                command_parts = data.split(":", 1)

                # silently ignore invalid commands
                if len(command_parts) == 2:
                    command, received_key = command_parts

                    # Secure comparison using constant time to prevent timing attacks
                    if command.lower() == "exit" and secrets.compare_digest(
                        received_key, secret_key
                    ):
                        # Set the shutdown event to signal all threads to exit
                        shutdown_event.set()
                        server_process.terminate()
                        break

                client_socket.close()
            except socket.timeout:
                continue
            except Exception as e:
                log.error(f"Error handling client connection: {e}")
    finally:
        server_socket.close()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        action=EnvDefault,
        envvar="FBS_PORT",
        help="Port for the server nanny [FBS_PORT]",
    )
    parser.add_argument(
        "--key",
        type=str,
        action=EnvDefault,
        envvar="FBS_KEY",
        help="Key for the server nanny [FBS_KEY]",
    )
    parser.add_argument(
        "--api-model",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_MODEL",
        help="HuggingFace model to serve [FBS_API_MODEL]",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_KEY",
        help="OpenAI-compatible REST API KEY [FBS_API_KEY]",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        action=EnvDefault,
        envvar="FBS_API_PORT",
        help="OpenAI-compatible REST API port [FBS_API_PORT]",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Event to signal shutdown to all threads
    shutdown_event: threading.Event = threading.Event()

    # Start server as a subprocess
    server_process: subprocess.Popen = start_server_process(
        args.api_model, args.api_port, args.api_key
    )

    # Start command listener in a separate thread
    listener: threading.Thread = threading.Thread(
        target=command_listener, args=(server_process, args.port, args.key)
    )
    listener.daemon = True
    listener.start()

    # Monitor the server process
    while server_process.poll() is None and not shutdown_event.is_set():
        time.sleep(1)

    # If server terminated unexpectedly, set shutdown event
    if not shutdown_event.is_set():
        log.warning("Server process terminated unexpectedly")
        shutdown_event.set()

    # Wait for the server process to terminate
    try:
        exit_code: Optional[int] = server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        log.warning("Server didn't terminate gracefully, killing...")
        server_process.kill()

    # Wait for the listener thread to finish
    listener.join(timeout=2)

    sys.exit(0)
