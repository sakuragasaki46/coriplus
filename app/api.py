from flask import Blueprint, jsonify, request
import sys, datetime
from functools import wraps
from .models import User, Message
from .utils import check_access_token, Visibility

bp = Blueprint('api', __name__, url_prefix='/api/V1')

def get_message_info(message):
    return {
        'id': message.id,
        'user': {
            'id': message.user.id,
            'username': message.user.username,
        },
        'text': message.text,
        'privacy': message.privacy,
        'pub_date': message.pub_date.timestamp()
    }

def validate_access(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        access_token = request.args.get('access_token')
        if access_token is None:
            return jsonify({
                'message': 'missing access_token',
                'status': 'fail'
            })
        user = check_access_token(access_token)
        if user is None:
            return jsonify({
                'message': 'invalid access_token',
                'status': 'fail'
            })
        try:
            result = func(user, *args, **kwargs)
            assert isinstance(result, dict)
        except Exception:
            sys.excepthook(*sys.exc_info())
            return jsonify({
                'message': str(sys.exc_info()[1]),
                'status': 'fail'
            })
        result['status'] = 'ok'
        return jsonify(result)
    return wrapper

@bp.route('/feed')
@validate_access
def feed(self):
    timeline_media = []
    date = request.args.get('offset')
    if date is None:
        date = datetime.datetime.now()
    else:
        date = datetime.datetime.fromtimestamp(date)
    query = Visibility(Message
        .select()
        .where(((Message.user << self.following())
            | (Message.user == self))
            & (Message.pub_date < date))
        .order_by(Message.pub_date.desc())
        .limit(20))
    for message in query:
        timeline_media.append(get_message_info(message))
    return {'timeline_media': timeline_media}
