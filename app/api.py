from flask import Blueprint, jsonify, request
import sys, datetime, re
from functools import wraps
from .models import User, Message, Relationship, \
    MSGPRV_PUBLIC, MSGPRV_UNLISTED, MSGPRV_FRIENDS, MSGPRV_ONLYME
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
            import traceback; traceback.print_exc()
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

@bp.route('/create', methods=['POST'])
@validate_access
def create(self):
    data = request.get_json(True)
    text = data['text']
    privacy = int(data.get('privacy', 0))
    message = Message.create(
        user=self,
        text=text,
        pub_date=datetime.datetime.now(),
        privacy=privacy)
    # Currently, API does not support files.
    # create mentions
    mention_usernames = set()
    for mo in re.finditer(r'\+([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)', text):
        mention_usernames.add(mo.group(1))
    # to avoid self mention
    mention_usernames.difference_update({self.username})
    for u in mention_usernames:
        try:
            mention_user = User.get(User.username == u)
            if privacy in (MSGPRV_PUBLIC, MSGPRV_UNLISTED) or \
                    (privacy == MSGPRV_FRIENDS and
                    mention_user.is_following(self) and 
                    self.is_following(mention_user)):
                push_notification('mention', mention_user, user=user.id)
        except User.DoesNotExist:
            pass

def get_relationship_info(self, other):
    if self == other:
        return
    return {
        "following": self.is_following(other),
        "followed_by": other.is_following(self)
    }

@bp.route('/profile_info/<userid>', methods=['GET'])
@validate_access
def profile_info(self, userid):
    if userid == 'self':
        user = self
    elif userid.startswith('+'):
        user = User.get(User.username == userid[1:])
    elif userid.isdigit():
        try:
            user = User[userid]
        except User.DoesNotExist:
            return {'user': None}
    else:
        raise ValueError('userid should be an integer or "self"')
    profile = user.profile
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "website": profile.website,
            "generation": profile.year,
            "instagram": profile.instagram,
            "facebook": profile.facebook,
            "relationships": get_relationship_info(self, user),
            "messages_count": len(user.messages),
            "followers_count": len(user.followers()),
            "following_count": len(user.following())
        }
    }

@bp.route('/profile_info/feed/<userid>', methods=['GET'])
@validate_access
def profile_feed(self, userid):
    if userid == 'self':
        user = self
    elif userid.startswith('+'):
        user = User.get(User.username == userid[1:])
    elif userid.isdigit():
        user = User[userid]
    else:
        raise ValueError('userid should be an integer or "self"')
    timeline_media = []
    date = request.args.get('offset')
    if date is None:
        date = datetime.datetime.now()
    else:
        date = datetime.datetime.fromtimestamp(date)
    query = Visibility(Message
        .select()
        .where((Message.user == user)
            & (Message.pub_date < date))
        .order_by(Message.pub_date.desc())
        .limit(20))
    for message in query:
        timeline_media.append(get_message_info(message))
    return {'timeline_media': timeline_media}

@bp.route('/profile_search', methods=['POST'])
@validate_access
def profile_search(self):
    data = request.get_json(True)
    query = User.select().where(User.username ** ('%' + data['q'] + '%')).limit(20)
    results = []
    for result in query:
        profile = result.profile
        results.append({
            "id": result.id,
            "username": result.username,
            "full_name": profile.full_name,
            "followers_count": len(result.followers())
        })
    return {
        "users": results
    }
        
