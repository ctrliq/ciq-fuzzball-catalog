#!/usr/bin/env python3
"""
OpenAI client
"""

import argparse
import logging
import os
import socket
import sys
import time
import yaml
import textwrap
from typing import Any, Dict, List
import openai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y%m%d %H:%M:%S",
)
log = logging.getLogger("llm_client_server.client")


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
        "--api-job",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_JOB",
        help="Name of job running OpenAI compatible REST API [FBS_API_JOB]",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        action=EnvDefault,
        envvar="FBS_API_PORT",
        help="Port for OpenAI compatible REST API [FBS_API_PORT]",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_KEY",
        help="KEY for OpenAI compatible REST API [FBS_API_KEY]",
    )
    parser.add_argument(
        "--api-model",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_MODEL",
        help="HuggingFace model served by host [FBS_API_MODEL]",
    )
    parser.add_argument(
        "--queries-file",
        type=str,
        action=EnvDefault,
        envvar="FBS_API_QUERIES",
        help="YAML file containing queries to run",
        default="queries.yaml",
    )
    return parser.parse_args()


def load_queries(file_path: str) -> List[Dict]:
    """Load queries from a YAML file."""
    try:
        with open(file_path, "r") as file:
            queries = yaml.safe_load(file)
            if not isinstance(queries, list):
                log.error(f"Queries file {file_path} must contain a list of queries")
                sys.exit(1)
            return queries
    except FileNotFoundError:
        log.error(f"Queries file {file_path} not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        log.error(f"Error parsing YAML file {file_path}: {e}")
        sys.exit(1)


def run_query(client, model: str, query: Dict, query_index: int):
    """Run a single query and print the result."""
    if not isinstance(query, dict) or "messages" not in query:
        log.error(
            f"Query {query_index} is invalid. Each query must have a 'messages' key."
        )
        return

    messages = query.get("messages", [])
    temperature = query.get("temperature", 0.2)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        query_desc = f"Query {query_index + 1}"
        if "description" in query:
            query_desc += f": {query['description']}"

        print(f"\n### {query_desc} {'#' * 40}")

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                short_content = content[:50] + "..." if len(content) > 50 else content
                print(f"{role.upper()}: {short_content}")

        print("\nRESPONSE:")
        print(textwrap.fill(completion.choices[0].message.content))

    except Exception as e:
        log.error(f"Error running query {query_index}: {e}")


def shutdown_server(host: str, port: int, key: str):
    """
    Sends the server the shutdown message.
    """
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        client_socket.sendall(f"exit:{key}".encode("utf-8"))
    except socket.error as e:
        log.error(f"Socket error: {e}")
    except Exception as e:
        log.error(f"Unexpected error occurred: {e}")
    finally:
        client_socket.close()


if __name__ == "__main__":
    args = parse_arguments()
    openai_api_base = f"http://{args.api_job}:{args.api_port}/v1"
    client = openai.OpenAI(
        api_key=args.api_key,
        base_url=openai_api_base,
    )

    # wait for server to be up
    while True:
        try:
            models = client.models.list()
        except openai.APIConnectionError:
            log.info("Waiting for server to become available")
            time.sleep(30)
        except openai.AuthenticationError:
            log.error("not authorized to access OpenAI server. This should not happen.")
            shutdown_server(args.api_job, args.port, args.key)
            sys.exit(1)
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            shutdown_server(args.api_job, args.port, args.key)
            sys.exit(1)
        else:
            log.info("Server is ready")
            break

    queries = load_queries(args.queries_file)
    log.info(f"Loaded {len(queries)} queries from {args.queries_file}")

    for i, query in enumerate(queries):
        run_query(client, args.api_model, query, i)

    shutdown_server(args.api_job, args.port, args.key)

    sys.exit(0)
