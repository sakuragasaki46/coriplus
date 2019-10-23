'''
A list of utilities used across modules.
'''

import datetime, re, base64, hashlib, string
from .models import User, Notification
from flask import abort, render_template, request, session
import sys, json

_forbidden_extensions = 'com net org txt'.split()
_username_characters = frozenset(string.ascii_letters + string.digits + '_')

def is_username(username):
    username_splitted = username.split('.')
    if username_splitted and username_splitted[-1] in _forbidden_extensions:
        return False
    return all(x and set(x) < _username_characters for x in username_splitted) 

def validate_birthday(date):
    today = datetime.date.today()
    if today.year - date.year > 13:
        return True
    if today.year - date.year < 13:
        return False
    if today.month > date.month:
        return True
    if today.month < date.month:
        return False
    if today.day >= date.day:
        return True
    return False

def validate_website(website):
    return re.match(r'(?:https?://)?(?:[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*'
        r'|\[[A-Fa-f0-9:]+\])(?::\d+)?(?:/[^\s]*)?(?:\?[^\s]*)?(?:#[^\s]*)?$',
        website)

def human_short_date(timestamp):
    return ''

def int_to_b64(n):
    b = int(n).to_bytes(48, 'big')
    return base64.b64encode(b).lstrip(b'A').decode()

def pwdhash(s):
    return hashlib.md5((request.form['password']).encode('utf-8')).hexdigest()

def get_object_or_404(model, *expressions):
    try:
        return model.get(*expressions)
    except model.DoesNotExist:
        abort(404)

class Visibility(object):
    '''
    Workaround for the visibility problem for posts.
    Cannot be directly resolved with filter().
    
    TODO find a better solution, this seems to be too slow.
    '''
    def __init__(self, query, is_public_timeline=False):
        self.query = query
        self.is_public_timeline = is_public_timeline
    def __iter__(self):
        for i in self.query:
            if i.is_visible(self.is_public_timeline):
                yield i
    def count(self):
        counter = 0
        for i in self.query:
            if i.is_visible(self.is_public_timeline):
                counter += 1
        return counter
    def paginate(self, page):
        counter = 0
        pages_no = range((page - 1) * 20, page * 20)
        for i in self.query:
            if i.is_visible(self.is_public_timeline):
                if counter in pages_no:
                    yield i
                counter += 1

def get_locations():
    data = {}
    with open('locations.txt') as f:
        for line in f:
            line = line.rstrip()
            if line.startswith('#'):
                continue
            try:
                key, value = line.split(None, 1)
            except ValueError:
                continue
            data[key] = value
    return data

try:
    locations = get_locations()
except OSError:
    locations = {}

# get the user from the session
# changed in 0.5 to comply with flask_login
def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User[user_id]

def push_notification(type, target, **kwargs):
    try:
        if isinstance(target, str):
            target = User.get(User.username == target)
        Notification.create(
            type=type,
            target=target,
            detail=json.dumps(kwargs),
            pub_date=datetime.datetime.now()
        )
    except Exception:
        sys.excepthook(*sys.exc_info())

def unpush_notification(type, target, **kwargs):
    try:
        if isinstance(target, str):
            target = User.get(User.username == target)
        (Notification
         .delete()
         .where(
            (Notification.type == type) &
            (Notification.target == target) &
            (Notification.detail == json.dumps(kwargs))
         )
         .execute())
    except Exception:
        sys.excepthook(*sys.exc_info())

# given a template and a SelectQuery instance, render a paginated list of
# objects from the query inside the template
def object_list(template_name, qr, var_name='object_list', **kwargs):
    kwargs.update(
        page=int(request.args.get('page', 1)),
        pages=qr.count() // 20 + 1)
    kwargs[var_name] = qr.paginate(kwargs['page'])
    return render_template(template_name, **kwargs)

def tokenize(characters, table):
    '''
    A useful tokenizer.
    '''
    pos = 0
    tokens = []
    while pos < len(characters):
        mo = None
        for pattern, tag in table:
            mo = re.compile(pattern).match(characters, pos)
            if mo:
                if tag:
                    text = mo.group(0)
                    tokens.append((text, tag))
                break
        pos = mo.end(0)
    return tokens
