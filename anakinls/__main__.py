# Copyright (C) 2020  Andrii Kolomoiets <andreyk.mad@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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

    parser.add_argument(
        '-v', action='store_true',
        help='Verbose output'
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

    if args.v:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger('pygls.protocol').setLevel(logging.DEBUG)

    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()


if __name__ == '__main__':
    main()
