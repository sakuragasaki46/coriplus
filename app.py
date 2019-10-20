from flask import (
    Flask, Markup, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for)
import hashlib
from peewee import *
import datetime, time, re, os, sys, string, json, html
from functools import wraps
import argparse
from flask_login import LoginManager, login_user, logout_user, login_required

__version__ = '0.6-dev'

# we want to support Python 3 only.
# Python 2 has too many caveats.
if sys.version_info[0] < 3:
    raise RuntimeError('Python 3 required')

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--norun', action='store_true', 
    help='Don\'t run the app. Useful for debugging.')
arg_parser.add_argument('-p', '--port', type=int, default=5000,
    help='The port where to run the app. Defaults to 5000')

app = Flask(__name__)
app.config.from_pyfile('config.py')

login_manager = LoginManager(app)

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

    # Helpers for flask_login
    def get_id(self):
        return str(self.id)
    @property
    def is_active(self):
        return not self.is_disabled
    @property
    def is_anonymous(self):
        return False
    @property
    def is_authenticated(self):
        return self == get_current_user()

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
    # user adminship is stored into a separate table; new in 0.6
    @property
    def is_admin(self):
        return UserAdminship.select().where(UserAdminship.user == self).exists()
    # user profile info; new in 0.6
    @property
    def profile(self):
        # lazy initialization; I don't want (and don't know how) 
        # to do schema changes.
        try:
            return UserProfile.get(UserProfile.user == self)
        except UserProfile.DoesNotExist:
            return UserProfile.create(user=self, full_name=self.username)

# User adminship.
# A very high privilege where users can review posts.
# For very few users only; new in 0.6
class UserAdminship(BaseModel):
    user = ForeignKeyField(User, primary_key=True)

# User profile.
# Additional info for identifying users.
# New in 0.6
class UserProfile(BaseModel):
    user = ForeignKeyField(User, primary_key=True)
    full_name = TextField()
    biography = TextField(default='')
    location = IntegerField(null=True)
    year = IntegerField(null=True)
    website = TextField(null=True)
    instagram = TextField(null=True)
    facebook = TextField(null=True)

# The message privacy values.
MSGPRV_PUBLIC = 0 # everyone
MSGPRV_UNLISTED = 1 # everyone, doesn't show up in public timeline
MSGPRV_FRIENDS = 2 # only accounts which follow each other
MSGPRV_ONLYME = 3 # only the poster

# A single public message.
# New in v0.5: removed type and info fields; added privacy field. 
class Message(BaseModel):
    # The user who posted the message.
    user = ForeignKeyField(User, backref='messages')
    # The text of the message.
    text = TextField()
    # The posted date.
    pub_date = DateTimeField()
    # Info about privacy of the message.
    privacy = IntegerField(default=MSGPRV_PUBLIC)

    def is_visible(self, is_public_timeline=False):
        user = self.user
        cur_user = get_current_user()
        privacy = self.privacy
        if user == cur_user:
            # short path
            # also: don't show user's messages in public timeline
            return not is_public_timeline
        elif privacy == MSGPRV_PUBLIC:
            return True
        elif privacy == MSGPRV_UNLISTED:
            # even if unlisted
            return not is_public_timeline
        elif privacy == MSGPRV_FRIENDS:
            if cur_user is None:
                return False
            return user.is_following(cur_user) and cur_user.is_following(user)
        else:
            return False

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

# fixing directory name because of imports from other directory
if __name__ != '__main__':
    UPLOAD_DIRECTORY = os.path.join(os.path.dirname(__file__), UPLOAD_DIRECTORY)
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
            User, UserAdminship, UserProfile, Message, Relationship, 
            Upload, Notification])
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

def validate_website(website):
    return re.match(r'(?:https?://)?(?:[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*'
        r'|\[[A-Fa-f0-9:]+\])(?::\d+)?(?:/[^\s]*)?(?:\?[^\s]*)?(?:#[^\s]*)?$',
        website)

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

login_manager.login_view = 'login'

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
    return render_template('404.html')

@app.route('/')
def homepage():
    if get_current_user():
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
            return render_template('join.html')
        if username == getattr(get_current_user(), 'username', None) and not request.form.get('confirm_another'):
            flash('You are already logged in. Please confirm you want to '
                  'create another account by checking the option.')
            return render_template('join.html')
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
                UserProfile.create(
                    user=user,
                    full_name=request.form.get('full_name') or username
                )

            # mark the user as being 'authenticated' by setting the session vars
            login_user(user)
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
            remember_for = int(request.form['remember'])
            if remember_for > 0:
                login_user(user, remember=True, 
                    duration=datetime.timedelta(days=remember_for))
            else:
                login_user(user)
            return redirect(request.args.get('next', '/'))
    return render_template('login.html')

@app.route('/logout/')
def logout():
    logout_user()
    flash('You were logged out')
    return redirect(request.args.get('next','/'))

@app.route('/+<username>/')
def user_detail(username):
    user = get_object_or_404(User, User.username == username)

    # get all the users messages ordered newest-first -- note how we're accessing
    # the messages -- user.message_set.  could also have written it as:
    # Message.select().where(Message.user == user)
    messages = Visibility(user.messages.order_by(Message.pub_date.desc()))
    # TODO change to "profile.html"
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
            user=user,
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

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    user = get_current_user()
    message = get_object_or_404(Message, Message.id == id)
    if message.user != user:
        abort(404)
    if request.method == 'POST' and (request.form['text'] != message.text or
            request.form['privacy'] != message.privacy):
        text = request.form['text']
        privacy = int(request.form.get('privacy', '0'))
        Message.update(
            text=text,
            privacy=privacy,
            pub_date=datetime.datetime.now()
        ).where(Message.id == id).execute()
        # edit uploads (skipped for now)
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
        flash('Your message has been edited successfully')
        return redirect(url_for('user_detail', username=user.username))
    return render_template('edit.html', message=message)

#@app.route('/delete/<int:id>', methods=['GET', 'POST'])
#def confirm_delete(id):
#    return render_template('confirm_delete.html')

@app.route('/edit_profile/', methods=['GET', 'POST'])
def edit_profile():
    if request.method == 'POST':
        user = get_current_user()
        username = request.form['username']
        if not username:
            # prevent username to be set to empty
            username = user.username
        if username != user.username:
            User.update(username=username).where(User.id == user.id).execute()
        website = request.form['website'].strip().replace(' ', '%20')
        if website and not validate_website(website):
            flash('You should enter a valid URL.')
            return render_template('edit_profile.html')
        location = int(request.form.get('location'))
        if location == 0:
            location = None
        UserProfile.update(
            full_name=request.form['full_name'] or username,
            biography=request.form['biography'],
            website=website,
            location=location
        ).where(UserProfile.user == user).execute()
        return redirect(url_for('user_detail', username=username))
    return render_template('edit_profile.html')

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

@app.route('/uploads/<id>.<type>')
def uploads(id, type='jpg'):
    return send_from_directory(UPLOAD_DIRECTORY, id + '.' + type)

@app.route('/ajax/username_availability/<username>')
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

@app.route('/ajax/location_search/<name>')
def location_search(name):
    results = []
    for key, value in locations.items():
        if value.startswith(name):
            results.append({'value': key, 'display': value})
    return jsonify({'results': results})

_enrich_symbols = [
    (r'\n', 'NEWLINE'),
    (r'https?://(?:[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*|\[[A-Fa-f0-9:]+\])'
     r'(?::\d+)?(?:/[^\s]*)?(?:\?[^\s]*)?(?:#[^\s]*)?', 'URL'),
    (_mention_re, 'MENTION'),
    (r'[^h\n+]+', 'TEXT'),
    (r'.', 'TEXT')
]

def _tokenize(characters, table):
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

@app.template_filter()
def enrich(s):
    tokens = _tokenize(s, _enrich_symbols)
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

# allow running from the command line
if __name__ == '__main__':
    args = arg_parser.parse_args()
    create_tables()
    if not args.norun:
        app.run(port=args.port)
