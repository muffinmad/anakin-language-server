import argparse
import inspect
import logging

from .server import server
from .version import get_version

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

    parser.add_argument(
        '--version', action='store_true',
        help='Print version and exit'
    )

    args = parser.parse_args()

    if args.version:
        print(inspect.cleandoc(f'''anakinls v{get_version()}
          Copyright (C) 2020 Andrii Kolomoiets
          This is free software; see the source for copying conditions.
          There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A
          PARTICULAR PURPOSE.
        '''))
        return

    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()


if __name__ == '__main__':
    main()
