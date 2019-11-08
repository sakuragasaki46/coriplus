'''
Database models for the application.

The tables are:
* user - the basic account info, such as username and password
* useradminship - relationship which existence determines whether a user is admin or not; new in 0.6
* userprofile - additional account info for self describing; new in 0.6
* message - a status update, appearing in profile and feeds
* relationship - a follow relationship between users
* upload - a file upload attached to a message; new in 0.2
* notification - a in-site notification to a user; new in 0.3
'''

from flask import request
from peewee import *
import os
# here should go `from .utils import get_current_user`, but it will cause
# import errors. It's instead imported at function level.

database = SqliteDatabase(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'coriplus.sqlite'))

class BaseModel(Model):
    class Meta:
        database = database

# A user. The user is separated from its page.
class User(BaseModel):
    # The unique username.
    username = CharField(unique=True)
    # The user's full name (here for better search since 0.8)
    full_name = TextField()
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
        from .utils import get_current_user
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
    biography = TextField(default='')
    location = IntegerField(null=True)
    year = IntegerField(null=True)
    website = TextField(null=True)
    instagram = TextField(null=True)
    facebook = TextField(null=True)
    telegram = TextField(null=True)
    @property
    def full_name(self):
        '''
        Moved to User in 0.8 for search improvement reasons.
        '''
        return self.user.full_name

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
        from .utils import get_current_user
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
            if cur_user.is_anonymous:
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


UPLOAD_DIRECTORY = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'uploads')

class Upload(BaseModel):
    # the extension of the media
    type = TextField()
    # the message bound to this media
    message = ForeignKeyField(Message, backref='uploads')
    # helper to retrieve contents
    def filename(self):
        return str(self.id) + '.' + self.type
    def url(self):
        return request.host_url + 'uploads/' + self.filename()

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
