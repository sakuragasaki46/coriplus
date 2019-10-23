'''
Run the app as module.

You can also use `flask run` on the parent directory of the package.

XXX Using "--debug" argument currently causes an ImportError.
'''

import argparse
from . import app
from .models import create_tables

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--norun', action='store_true', 
    help='Don\'t run the app. Useful for debugging.')
arg_parser.add_argument('--no-create-tables', action='store_true',
    help='Don\'t create tables.')
arg_parser.add_argument('--debug', action='store_true', 
    help='Run the app in debug mode.')
arg_parser.add_argument('-p', '--port', type=int, default=5000,
    help='The port where to run the app. Defaults to 5000')

args = arg_parser.parse_args()

if not args.no_create_tables:
    create_tables()

if not args.norun:
    app.run(port=args.port, debug=args.debug)
