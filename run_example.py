#!/usr/bin/env python

import sys
sys.path.insert(0, '../..')

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=5000,
    help='An alternative port where to run the server.')

from app import app, create_tables

if __name__ == '__main__':
    args = argparse.parse_args()
    create_tables()
    app.run(port=args.port)
