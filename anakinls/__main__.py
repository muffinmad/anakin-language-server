import argparse
import logging

from .server import server

logging.basicConfig(level=logging.INFO)
logging.getLogger('pygls.protocol').setLevel(logging.WARN)


def main():
    parser = argparse.ArgumentParser()
    parser.description = 'Yet another Jedi Python language server'

    parser.add_argument(
        '--tcp', action='store_true',
        help='Use TCP server instead of stdio'
    )

    parser.add_argument(
        '--host', default='127.0.0.1',
        help='Bind to this address'
    )

    parser.add_argument(
        '--port', type=int, default=2087,
        help='Bind to this port'
    )

    args = parser.parse_args()

    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()


if __name__ == '__main__':
    main()
