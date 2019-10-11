from flask import (
    Flask, Markup, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for)
import hashlib
from peewee import *
import datetime, time, re, os, sys, string, json
from functools import wraps

__version__ = '0.4.0'

# we want to support Python 3 only.
# Python 2 has too many caveats.
if sys.version_info[0] < 3:
    raise RuntimeError('Python 3 required')
   
app = Flask(__name__)
app.config.from_pyfile('config.py')

### DATABASE ###

database = SqliteDatabase(app.config['DATABASE'])

class BaseModel(Model):
    class Meta:
        database = database

# A user. The user is separated from its page.
class User(BaseModel):
    # The unique username.
    username = CharField(unique=True)
    # The password hash.
    password = CharField()
    # An email address.
    email = CharField()
    # The date of birth (required because of Terms of Service)
    birthday = DateField()
    # The date joined
    join_date = DateTimeField()
    # A disabled flag. 0 = active, 1 = disabled by user, 2 = banned
    is_disabled = IntegerField(default=0)

    # it often makes sense to put convenience methods on model instances, for
    # example, "give me all the users this user is following":
    def following(self):
        # query other users through the "relationship" table
        return (User
                .select()
                .join(Relationship, on=Relationship.to_user)
                .where(Relationship.from_user == self)
                .order_by(User.username))

    def followers(self):
        return (User
                .select()
                .join(Relationship, on=Relationship.from_user)
                .where(Relationship.to_user == self)
                .order_by(User.username))

    def is_following(self, user):
        return (Relationship
                .select()
                .where(
                    (Relationship.from_user == self) &
                    (Relationship.to_user == user))
                .exists())

    def unseen_notification_count(self):
        return len(Notification
                .select()
                .where(
                    (Notification.target == self) & (Notification.seen == 0)
                ))

# A single public message.
class Message(BaseModel):
    # The type of the message. 
    type = TextField()
    # The user who posted the message.
    user = ForeignKeyField(User, backref='messages')
    # The text of the message.
    text = TextField()
    # Additional info (in JSON format)
    # TODO: remove because it's dumb.
    info = TextField(default='{}')
    # The posted date.
    pub_date = DateTimeField()
    # Info about privacy of the message.
    @property
    def privacy(self):
        try:
            return MessagePrivacy.get(MessagePrivacy.message == self).value
        except MessagePrivacy.DoesNotExist:
            # default to public
            return MSGPRV_PUBLIC
    def is_visible(self, is_public_timeline=False):
        user = self.user
        cur_user = get_current_user()
        privacy = self.privacy
        if user == cur_user:
            # short path
            return True
        elif privacy == MSGPRV_PUBLIC:
            return True
        elif privacy == MSGPRV_UNLISTED:
            # TODO user's posts may appear the same in public timeline,
            # even if unlisted
            return not is_public_timeline
        elif privacy == MSGPRV_FRIENDS:
            if cur_user is None:
                return False
            return user.is_following(cur_user) and cur_user.is_following(user)
        else:
            return False

# The message privacy values.
MSGPRV_PUBLIC = 0 # everyone
MSGPRV_UNLISTED = 1 # everyone, doesn't show up in public timeline
MSGPRV_FRIENDS = 2 # only accounts which follow each other
MSGPRV_ONLYME = 3 # only the poster

# Doing it into a separate table to don't worry about schema change.
# Added in v0.4.
class MessagePrivacy(BaseModel):
    # The message.
    message = ForeignKeyField(Message, primary_key=True)
    # The privacy value. Needs to be one of these above.
    value = IntegerField()

# this model contains two foreign keys to user -- it essentially allows us to
# model a "many-to-many" relationship between users.  by querying and joining
# on different columns we can expose who a user is "related to" and who is
# "related to" a given user
class Relationship(BaseModel):
    from_user = ForeignKeyField(User, backref='relationships')
    to_user = ForeignKeyField(User, backref='related_to')
    created_date = DateTimeField()

    class Meta:
        indexes = (
            # Specify a unique multi-column index on from/to-user.
            (('from_user', 'to_user'), True),
        )


UPLOAD_DIRECTORY = 'uploads/'
class Upload(BaseModel):
    # the extension of the media
    type = TextField()
    # the message bound to this media
    message = ForeignKeyField(Message, backref='uploads')
    # helper to retrieve contents
    def filename(self):
        return str(self.id) + '.' + self.type

class Notification(BaseModel):
    type = TextField()
    target = ForeignKeyField(User, backref='notifications')
    detail = TextField()
    pub_date = DateTimeField()
    seen = IntegerField(default=0)

def create_tables():
    with database:
        database.create_tables([
            User, Message, Relationship, Upload, Notification, MessagePrivacy])
    if not os.path.isdir(UPLOAD_DIRECTORY):
        os.makedirs(UPLOAD_DIRECTORY)

### UTILS ###

_forbidden_extensions = 'com net org txt'.split()
_username_characters = frozenset(string.ascii_letters + string.digits + '_')

def is_username(username):
    username_splitted = username.split('.')
    if username_splitted and username_splitted[-1] in _forbidden_extensions:
        return False
    return all(x and set(x) < _username_characters for x in username_splitted)

_mention_re = r'\+([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)'

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

def human_short_date(timestamp):
    return ''

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

# flask provides a "session" object, which allows us to store information across
# requests (stored by default in a secure cookie).  this function allows us to
# mark a user as being logged-in by setting some values in the session data:
def auth_user(user):
    session['logged_in'] = True
    session['user_id'] = user.id
    session['username'] = user.username
    flash('You are logged in as %s' % (user.username))

# get the user from the session
def get_current_user():
    if session.get('logged_in'):
        return User.get(User.id == session['user_id'])

# view decorator which indicates that the requesting user must be authenticated
# before they can access the view.  it checks the session to see if they're
# logged in, and if not redirects them to the login view.
def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return inner

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

### WEB ###

@app.before_request
def before_request():
    g.db = database
    g.db.connect()

@app.after_request
def after_request(response):
    g.db.close()
    return response

@app.context_processor
def _inject_user():
    return {'current_user': get_current_user()}

@app.errorhandler(404)
def error_404(body):
    return render_template('404.html')

@app.route('/')
def homepage():
    if session.get('logged_in'):
        return private_timeline()
    else:
        return render_template('homepage.html')

def private_timeline():
    # the private timeline (aka feed) exemplifies the use of a subquery -- we are asking for
    # messages where the person who created the message is someone the current
    # user is following.  these messages are then ordered newest-first.
    user = get_current_user()
    messages = Visibility(Message
                .select()
                .where((Message.user << user.following())
                       | (Message.user == user))
                .order_by(Message.pub_date.desc()))
    # TODO change to "feed.html"
    return object_list('private_messages.html', messages, 'message_list')

@app.route('/explore/')
def public_timeline():
    messages = Visibility(Message
                .select()
                .order_by(Message.pub_date.desc()), True)
    return object_list('explore.html', messages, 'message_list')

@app.route('/signup/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST' and request.form['username']:
        try:
            birthday = datetime.datetime.fromisoformat(request.form['birthday'])
        except ValueError:
            flash('Invalid date format')
            return render_template('join.html')
        username = request.form['username'].lower()
        if not is_username(username):
            flash('This username is invalid')
        try:
            with database.atomic():
                # Attempt to create the user. If the username is taken, due to the
                # unique constraint, the database will raise an IntegrityError.
                user = User.create(
                    username=username,
                    password=pwdhash(request.form['password']),
                    email=request.form['email'],
                    birthday=birthday,
                    join_date=datetime.datetime.now())

            # mark the user as being 'authenticated' by setting the session vars
            auth_user(user)
            return redirect(request.args.get('next','/'))

        except IntegrityError:
            flash('That username is already taken')

    return render_template('join.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['username']:
        try:
            username = request.form['username']
            pw_hash = pwdhash(request.form['password'])
            if '@' in username:
                user = User.get(User.email == username)
            else:
                user = User.get(User.username == username)
            if user.password != pw_hash:
                flash('The password entered is incorrect.')
                return render_template('login.html')
        except User.DoesNotExist:
            flash('A user with this username or email does not exist.')
        else:
            auth_user(user)
            return redirect(request.args.get('next', '/'))
    return render_template('login.html')

@app.route('/logout/')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(request.args.get('next','/'))

@app.route('/+<username>/')
def user_detail(username):
    user = get_object_or_404(User, User.username == username)

    # get all the users messages ordered newest-first -- note how we're accessing
    # the messages -- user.message_set.  could also have written it as:
    # Message.select().where(Message.user == user)
    messages = Visibility(user.messages.order_by(Message.pub_date.desc()))
    return object_list('user_detail.html', messages, 'message_list', user=user)

@app.route('/+<username>/follow/', methods=['POST'])
@login_required
def user_follow(username):
    cur_user = get_current_user()
    user = get_object_or_404(User, User.username == username)
    try:
        with database.atomic():
            Relationship.create(
                from_user=cur_user,
                to_user=user,
                created_date=datetime.datetime.now())
    except IntegrityError:
        pass

    flash('You are following %s' % user.username)
    push_notification('follow', user, user=cur_user.id)
    # TODO change to "profile.html"
    return redirect(url_for('user_detail', username=user.username))

@app.route('/+<username>/unfollow/', methods=['POST'])
@login_required
def user_unfollow(username):
    cur_user = get_current_user()
    user = get_object_or_404(User, User.username == username)
    (Relationship
     .delete()
     .where(
         (Relationship.from_user == cur_user) &
         (Relationship.to_user == user))
     .execute())
    flash('You are no longer following %s' % user.username)
    unpush_notification('follow', user, user=cur_user.id)
    return redirect(url_for('user_detail', username=user.username))


@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    user = get_current_user()
    if request.method == 'POST' and request.form['text']:
        text = request.form['text']
        privacy = int(request.form.get('privacy', '0'))
        message = Message.create(
            type='text',
            user=user,
            text=text,
            pub_date=datetime.datetime.now())
        MessagePrivacy.create(
            message=message,
            value=privacy
        )
        file = request.files.get('file')
        if file:
            print('Uploading', file.filename)
            ext = file.filename.split('.')[-1]
            upload = Upload.create(
                type=ext,
                message=message
            )
            file.save(UPLOAD_DIRECTORY + str(upload.id) + '.' + ext)
        # create mentions
        mention_usernames = set()
        for mo in re.finditer(_mention_re, text):
            mention_usernames.add(mo.group(1))
        # to avoid self mention
        mention_usernames.difference_update({user.username})
        for u in mention_usernames:
            try:
                mention_user = User.get(User.username == u)
                if privacy in (MSGPRV_PUBLIC, MSGPRV_UNLISTED) or \
                        (privacy == MSGPRV_FRIENDS and
                        mention_user.is_following(user) and 
                        user.is_following(mention_user)):
                    push_notification('mention', mention_user, user=user.id)
            except User.DoesNotExist:
                pass
        flash('Your message has been posted successfully')
        return redirect(url_for('user_detail', username=user.username))
    return render_template('create.html')

@app.route('/notifications/')
@login_required
def notifications():
    user = get_current_user()
    notifications = (Notification
                     .select()
                     .where(Notification.target == user)
                     .order_by(Notification.pub_date.desc()))

    with database.atomic():
        (Notification
         .update(seen=1)
         .where((Notification.target == user) & (Notification.seen == 0))
         .execute())
    return object_list('notifications.html', notifications, 'notification_list', json=json, User=User)

@app.route('/about/')
def about():
    return render_template('about.html', version=__version__)

# The two following routes are mandatory by law.
@app.route('/terms/')
def terms():
    return render_template('terms.html')

@app.route('/privacy/')
def privacy():
    return render_template('privacy.html')

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.getcwd(), 'robots.txt')

@app.route('/uploads/<id>.jpg')
def uploads(id, type='jpg'):
    return send_from_directory(UPLOAD_DIRECTORY, id + '.' + type)

@app.route('/ajax/username_availability/<username>')
def username_availability(username):
    if session.get('logged_in'):
        current = get_current_user().username
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

@app.template_filter()
def enrich(s):
    '''Filter for mentioning users.'''
    return Markup(re.sub(_mention_re, r'<a href="/+\1">\1</a>', s))

@app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)


# allow running from the command line
if __name__ == '__main__':
    create_tables()
    app.run()
