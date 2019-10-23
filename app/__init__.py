'''
Cori+
=====

The root module of the package.
This module also contains very basic web hooks, such as robots.txt.

For the website hooks, see `app.website`.
For the AJAX hook, see `app.ajax`.
For template filters, see `app.filters`.
For the database models, see `app.models`.
For other, see `app.utils`.
'''

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for, __version__ as flask_version)
import hashlib
from peewee import *
import datetime, time, re, os, sys, string, json, html
from functools import wraps
from flask_login import LoginManager

__version__ = '0.7-dev'

# we want to support Python 3 only.
# Python 2 has too many caveats.
if sys.version_info[0] < 3:
    raise RuntimeError('Python 3 required')

app = Flask(__name__)
app.config.from_pyfile('../config.py')

login_manager = LoginManager(app)

from .models import *

from .utils import *

from .filters import *

### WEB ###

login_manager.login_view = 'website.login'

@app.before_request
def before_request():
    g.db = database
    try:
        g.db.connect()
    except OperationalError:
        sys.stderr.write('database connected twice.\n')

@app.after_request
def after_request(response):
    g.db.close()
    return response

@app.context_processor
def _inject_variables():
    return {'site_name': app.config['SITE_NAME'], 'locations': locations}

@login_manager.user_loader
def _inject_user(userid):
    return User[userid]

@app.errorhandler(404)
def error_404(body):
    return render_template('404.html'), 404

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.getcwd(), 'robots.txt')

@app.route('/uploads/<id>.<type>')
def uploads(id, type='jpg'):
    return send_from_directory(UPLOAD_DIRECTORY, id + '.' + type)

from .website import bp
app.register_blueprint(bp)

from .ajax import bp
app.register_blueprint(bp)




