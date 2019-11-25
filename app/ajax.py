'''
AJAX hooks for the website.

Warning: this is not the public API.
'''

from flask import Blueprint, jsonify
from .models import User, Message, MessageUpvote
from .utils import locations, get_current_user, is_username
import datetime

bp = Blueprint('ajax', __name__, url_prefix='/ajax')

@bp.route('/username_availability/<username>')
def username_availability(username):
    current = get_current_user()
    if current:
        current = current.username
    else:
        current = None
    is_valid = is_username(username)
    if is_valid:
        try:
            user = User.get(User.username == username)
            is_available = current == user.username
        except User.DoesNotExist:
            is_available = True
    else:
        is_available = False
    return jsonify({'is_valid':is_valid, 'is_available':is_available, 'status':'ok'})

@bp.route('/location_search/<name>')
def location_search(name):
    results = []
    for key, value in locations.items():
        if value.lower().startswith(name.lower()):
            results.append({'value': key, 'display': value})
    return jsonify({'results': results})

@bp.route('/score/<int:id>/toggle', methods=['POST'])
def score_toggle(id):
    user = get_current_user()
    message = Message[id]
    upvoted_by_self = (MessageUpvote
            .select()
            .where((MessageUpvote.message == message) & (MessageUpvote.user == user))
            .exists())
    if upvoted_by_self:
        (MessageUpvote
         .delete()
         .where(
            (MessageUpvote.message == message) &
            (MessageUpvote.user == user))
         .execute()
        )
    else:
        MessageUpvote.create(
            message=message,
            user=user,
            created_date=datetime.datetime.now()
        )
    return jsonify({
        "score": message.score,
        "status": "ok"
    })
