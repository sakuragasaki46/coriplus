'''
All website hooks, excluding AJAX.
'''

from .utils import *
from .models import *
from . import __version__ as app_version
from sys import version as python_version
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, __version__ as flask_version
from flask_login import login_required, login_user, logout_user
import json

bp = Blueprint('website', __name__)

@bp.route('/')
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
    return object_list('feed.html', messages, 'message_list')

@bp.route('/explore/')
def public_timeline():
    messages = Visibility(Message
                .select()
                .order_by(Message.pub_date.desc()), True)
    return object_list('explore.html', messages, 'message_list')

@bp.route('/signup/', methods=['GET', 'POST'])
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
                    full_name=request.form.get('full_name') or username,
                    password=pwdhash(request.form['password']),
                    email=request.form['email'],
                    birthday=birthday,
                    join_date=datetime.datetime.now())
                UserProfile.create(
                    user=user
                )

            # mark the user as being 'authenticated' by setting the session vars
            login_user(user)
            return redirect(request.args.get('next','/'))

        except IntegrityError:
            flash('That username is already taken')

    return render_template('join.html')

@bp.route('/login/', methods=['GET', 'POST'])
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

@bp.route('/logout/')
def logout():
    logout_user()
    flash('You were logged out')
    return redirect(request.args.get('next','/'))

@bp.route('/+<username>/')
def user_detail(username):
    user = get_object_or_404(User, User.username == username)

    # get all the users messages ordered newest-first -- note how we're accessing
    # the messages -- user.message_set.  could also have written it as:
    # Message.select().where(Message.user == user)
    messages = Visibility(user.messages.order_by(Message.pub_date.desc()))
    # TODO change to "profile.html"
    return object_list('user_detail.html', messages, 'message_list', user=user)

@bp.route('/+<username>/follow/', methods=['POST'])
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
    return redirect(url_for('website.user_detail', username=user.username))

@bp.route('/+<username>/unfollow/', methods=['POST'])
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
    return redirect(url_for('website.user_detail', username=user.username))

@bp.route('/+<username>/followers/')
@login_required
def user_followers(username):
    user = get_object_or_404(User, User.username == username)
    return object_list('user_list.html', user.followers(), 'user_list',
                       title='%s\'s followers' % username)

@bp.route('/+<username>/following/')
@login_required
def user_following(username):
    user = get_object_or_404(User, User.username == username)
    return object_list('user_list.html', user.following(), 'user_list',
                       title='Accounts followed by %s' % username)

@bp.route('/create/', methods=['GET', 'POST'])
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
        for mo in re.finditer(r'\+([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)', text):
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
        return redirect(url_for('website.user_detail', username=user.username))
    return render_template('create.html')

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
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
        for mo in re.finditer(r'\+([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)', text):
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
        return redirect(url_for('website.user_detail', username=user.username))
    return render_template('edit.html', message=message)

@bp.route('/delete/<int:id>', methods=['GET', 'POST'])
def confirm_delete(id):
    user = get_current_user()
    message = get_object_or_404(Message, Message.id == id)
    if message.user != user:
        abort(404)
    if request.method == 'POST':
        abort(501, 'CSRF-Token missing.')
    return render_template('confirm_delete.html', message=message)

# Workaround for problems related to invalid data.
# Without that, changes will be lost across requests.
def profile_checkpoint():
    return UserProfile(
        user=get_current_user(),
        biography=request.form['biography'],
        location=int(request.form['location']),
        year=int(request.form['year'] if request.form.get('has_year') else '0'),
        website=request.form['website'] or None,
        instagram=request.form['instagram'] or None,
        facebook=request.form['facebook'] or None,
        telegram=request.form['telegram'] or None
    )

@bp.route('/edit_profile/', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        user = get_current_user()
        username = request.form['username']
        if not username:
            # prevent username to be set to empty
            username = user.username
        if username != user.username:
            try:
                User.update(username=username).where(User.id == user.id).execute()
            except IntegrityError:
                flash('That username is already taken')
                return render_template('edit_profile.html', profile=profile_checkpoint())
        full_name = request.form['full_name'] or username
        if full_name != user.full_name:
            User.update(full_name=full_name).where(User.id == user.id).execute()
        website = request.form['website'].strip().replace(' ', '%20')
        if website and not validate_website(website):
            flash('You should enter a valid URL.')
            return render_template('edit_profile.html', profile=profile_checkpoint())
        location = int(request.form.get('location'))
        if location == 0:
            location = None
        UserProfile.update(
            biography=request.form['biography'],
            year=request.form['year'] if request.form.get('has_year') else None,
            location=location,
            website=website,
            instagram=request.form['instagram'],
            facebook=request.form['facebook'],
            telegram=request.form['telegram']
        ).where(UserProfile.user == user).execute()
        return redirect(url_for('website.user_detail', username=username))
    return render_template('edit_profile.html')

@bp.route('/change_password/', methods=['GET', 'POST'])
def change_password():
    user = get_current_user()
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        errors = False
        if not new_password:
            flash('Password cannot be empty')
            errors = True
        if new_password != confirm_password:
            flash('Password mismatch')
            errors = True
        if pwdhash(old_password) != user.password:
            flash('The old password is incorrect')
            errors = True 
        if not errors:
            user.update(
                password=pwdhash(new_password)
            )
            return redirect(url_for('website.edit_profile'))
    return render_template('change_password.html')

@bp.route('/notifications/')
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

@bp.route('/about/')
def about():
    return render_template('about.html', version=app_version,
        python_version=python_version, flask_version=flask_version)

# The two following routes are mandatory by law.
@bp.route('/terms/')
def terms():
    return render_template('terms.html')

@bp.route('/privacy/')
def privacy():
    return render_template('privacy.html')


