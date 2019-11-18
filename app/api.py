from flask import Blueprint, jsonify, request
import sys, os, datetime, re
from functools import wraps
from peewee import IntegrityError
from .models import User, Message, Upload, Relationship, database, \
    MSGPRV_PUBLIC, MSGPRV_UNLISTED, MSGPRV_FRIENDS, MSGPRV_ONLYME, UPLOAD_DIRECTORY
from .utils import check_access_token, Visibility, push_notification, unpush_notification, \
    create_mentions, is_username

bp = Blueprint('api', __name__, url_prefix='/api/V1')

def get_message_info(message):
    try:
        media = message.uploads[0].url()
    except IndexError:
        media = None
    if media:
        print(media)
    return {
        'id': message.id,
        'user': {
            'id': message.user.id,
            'username': message.user.username,
        },
        'text': message.text,
        'privacy': message.privacy,
        'pub_date': message.pub_date.timestamp(),
        'media': media
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
    # This API does not support files. Use create2 instead.
    create_mentions(self, text)
    return {}

@bp.route('/create2', methods=['POST'])
@validate_access
def create2(self):
    text = request.form['text']
    privacy = int(request.form.get('privacy', 0))
    message = Message.create(
        user=self,
        text=text,
        pub_date=datetime.datetime.now(),
        privacy=privacy)
    file = request.files.get('file')
    if file:
        print('Uploading', file.filename)
        ext = file.filename.split('.')[-1]
        upload = Upload.create(
            type=ext,
            message=message
        )
        file.save(os.path.join(UPLOAD_DIRECTORY, str(upload.id) + '.' + ext))
    create_mentions(self, text)
    return {}

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

@bp.route('/relationships/<int:userid>/follow', methods=['POST'])
@validate_access
def relationships_follow(self, userid):
    user = User[userid]
    try:
        with database.atomic():
            Relationship.create(
                from_user=self,
                to_user=user,
                created_date=datetime.datetime.now())
    except IntegrityError:
        pass
    push_notification('follow', user, user=self.id)
    return get_relationship_info(self, user)

@bp.route('/relationships/<int:userid>/unfollow', methods=['POST'])
@validate_access
def relationships_unfollow(self, userid):
    user = User[userid]
    (Relationship
     .delete()
     .where(
         (Relationship.from_user == self) &
         (Relationship.to_user == user))
     .execute())
    unpush_notification('follow', user, user=self.id)
    return get_relationship_info(self, user)

@bp.route('/profile_search', methods=['POST'])
@validate_access
def profile_search(self):
    data = request.get_json(True)
    query = User.select().where((User.username ** ('%' + data['q'] + '%')) |
        (User.full_name ** ('%' + data['q'] + '%'))).limit(20)
    results = []
    for result in query:
        profile = result.profile
        results.append({
            "id": result.id,
            "username": result.username,
            "full_name": result.full_name,
            "followers_count": len(result.followers())
        })
    return {
        "users": results
    }

@bp.route('/username_availability/<username>')
@validate_access
def username_availability(self, username):
    current = self.username
    is_valid = is_username(username)
    if is_valid:
        try:
            user = User.get(User.username == username)
            is_available = current == user.username
        except User.DoesNotExist:
            is_available = True
    else:
        is_available = False
    return {
        'is_valid': is_valid,
        'is_available': is_available
    }

@bp.route('/edit_profile', methods=['POST'])
@validate_access
def edit_profile(user):
    data = request.get_json(True)
    username = data['username']
    if not username:
        # prevent username to be set to empty
        username = user.username
    if username != user.username:
        try:
            User.update(username=username).where(User.id == user.id).execute()
        except IntegrityError:
            raise ValueError('that username is already taken')
    full_name = data['full_name'] or username
    if full_name != user.full_name:
        User.update(full_name=full_name).where(User.id == user.id).execute()
    website = data['website'].strip().replace(' ', '%20')
    if website and not validate_website(website):
        raise ValueError('You should enter a valid URL.')
    #location = int(request.form.get('location'))
    #if location == 0:
    #    location = None
    UserProfile.update(
        biography=data['biography'],
        #year=data['year'] if data.get('has_year') else None,
        #location=location,
        website=website,
        instagram=data['instagram'],
        facebook=data['facebook'],
        telegram=data['telegram']
    ).where(UserProfile.user == user).execute()
    return {}

@bp.route('/request_edit/<int:id>')
@validate_access
def request_edit(self, id):
    message = Message[id]
    if message.user != self:
        raise ValueError('Attempt to edit a message from another')
    return {
        'message_info': get_message_info(message)
    }

@bp.route('/save_edit/<int:id>', methods=['POST'])
@validate_access
def save_edit(self, id):
    message = Message[id]
    if message.user != self:
        raise ValueError('Attempt to edit a message from another')
    data = request.get_json(True)
    Message.update(text=data['text'], privacy=data['privacy']).where(Message.id == id).execute()
    return {}
