'''
Filter functions used in the website templates.
'''

from flask import Markup
import html, datetime, re, time
from .utils import tokenize
from . import app

@app.template_filter()
def human_date(date):
    timestamp = date.timestamp()
    today = int(time.time())
    offset = today - timestamp
    if offset <= 1:
        return '1 second ago'
    elif offset < 60:
        return '%d seconds ago' % offset
    elif offset < 120:
        return '1 minute ago'
    elif offset < 3600:
        return '%d minutes ago' % (offset // 60)
    elif offset < 7200:
        return '1 hour ago'
    elif offset < 86400:
        return '%d hours ago' % (offset // 3600)
    elif offset < 172800:
        return '1 day ago'
    elif offset < 604800:
        return '%d days ago' % (offset // 86400)
    else:
        d = datetime.datetime.fromtimestamp(timestamp)
        return d.strftime('%B %e, %Y')

_enrich_symbols = [
    (r'\n', 'NEWLINE'),
    (r'https?://(?:[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*|\[[A-Fa-f0-9:]+\])'
     r'(?::\d+)?(?:/[^\s]*)?(?:\?[^\s]*)?(?:#[^\s]*)?', 'URL'),
    (r'\+([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)', 'MENTION'),
    (r'[^h\n+]+', 'TEXT'),
    (r'.', 'TEXT')
]

@app.template_filter()
def enrich(s):
    tokens = tokenize(s, _enrich_symbols)
    r = []
    for text, tag in tokens:
        if tag == 'TEXT':
            r.append(html.escape(text))
        elif tag == 'URL':
            r.append('<a href="{0}">{0}</a>'.format(html.escape(text)))
        elif tag == 'MENTION':
            r.append('<span class="weak">+</span><a href="/{0}">{1}</a>'.format(text, text.lstrip('+')))
        elif tag == 'NEWLINE':
            r.append('<br>')
    return Markup(''.join(r))

@app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)

@app.template_filter('locationdata')
def locationdata(key):
    if key > 0:
        return locations[str(key)]
