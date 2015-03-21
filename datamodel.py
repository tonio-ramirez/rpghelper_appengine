'''
Created on Mar 30, 2009

@author: Tonio
'''

from google.appengine.ext import db
from google.appengine.ext import search
from google.appengine.api import users
from google.appengine.api.datastore_errors import BadValueError
import hashlib
from datetime import datetime
import cPickle
import zlib
import tzsearch

class DictionaryProperty(db.Property):
    data_type = db.Blob

    _tfm = [cPickle.dumps, zlib.compress]
    _itfm = [zlib.decompress, cPickle.loads]

    def empty(self, value):
        return not value

    def validate(self, value):
        if value and not isinstance(value,dict):
            raise BadValueError('Property %s must be convertible '
                                'to a dict instance (%s)' %
                                (self.name, value))
        return super(DictionaryProperty, self).validate(value)

    def get_value_for_datastore(self, model_instance):
        value = super(DictionaryProperty,
                      self).get_value_for_datastore(model_instance)

        if value is not None:
            value = self.data_type(reduce(lambda x, f: f(x), self._tfm, value))
        return value

    def make_value_from_datastore(self, value):
        if value is not None:
            value = reduce(lambda x, f: f(x), self._itfm, value)

        return value if value else {}

class Campaign(db.Model):
    owner = db.UserProperty(auto_current_user_add=True)
    name = db.StringProperty()
    type = db.StringProperty()

class DiceRoll(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    stamp = db.DateTimeProperty(auto_now_add=True)
    order_key = db.StringProperty()
    use = db.StringProperty()
    description = db.StringProperty()
    total = db.IntegerProperty()
    adder = db.IntegerProperty()
    half = db.BooleanProperty()
    rolls = db.ListProperty(int)
    die_faces = db.IntegerProperty()
    campaign = db.ReferenceProperty(Campaign)
    match_start = db.IntegerProperty()
    match_end = db.IntegerProperty()

    def _is_max(self):
        if self.campaign.type == 'Champions':
            return self.description == '3d6' and self.total == 18
        elif self.campaign.type == 'D&D':
            return len(self.rolls) == 1 and self.die_faces == 20 and not self.half and self.rolls[0] == 20
        else:
            return False

    def _is_min(self):
        if self.campaign.type == 'Champions':
            return self.description == '3d6' and self.total == 3
        elif self.campaign.type == 'D&D':
            return len(self.rolls) == 1 and self.die_faces == 20 and not self.half and self.rolls[0] == 1
        else:
            return False

class ChatMessage(tzsearch.SearchableModel):
    @classmethod
    def SearchableProperties(cls):
        return [['message']]

    user = db.UserProperty(auto_current_user_add=True)
    stamp = db.DateTimeProperty(auto_now_add=True)
    order_key = db.StringProperty()
    campaign = db.ReferenceProperty(Campaign)
    message = db.TextProperty()

class ChatMessageNotification(db.Model):
    user_nick = db.StringProperty()
    campaign_id = db.IntegerProperty()

class UserPrefs(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    campaign = db.ReferenceProperty(Campaign)
    timezone = db.StringProperty(default='GMT')
    count = db.IntegerProperty(default=0)
    chatCount = db.IntegerProperty(default=0)
    last_access = db.DateTimeProperty()
    latest_read_message_by_campaign = DictionaryProperty()
    last_notification_by_campaign = DictionaryProperty()
    nickname = db.StringProperty()
    client_id_counter = db.IntegerProperty(default=0)

class CampaignSubscription(db.Model):
    campaign = db.ReferenceProperty(Campaign)
    subscribed = db.BooleanProperty(default=True)

class OpenChannel(db.Model):
    clientId = db.StringProperty()
    campaign = db.ReferenceProperty(Campaign)
    expiration = db.DateTimeProperty()

def subscribe_to_campaign(user_prefs, campaign):
    camp_subs = CampaignSubscription.all().ancestor(user_prefs).filter('campaign =', campaign).get()
    if not camp_subs:
        camp_subs = CampaignSubscription(parent=user_prefs.key())
        camp_subs.campaign = campaign
        camp_subs.put()
    elif not camp_subs.subscribed:
        camp_subs.subscribed = True
        camp_subs.put()

def generate_client_id(user_prefs):
    def txn():
        ctr = user_prefs.client_id_counter
        user_prefs.client_id_counter += 1
        user_prefs.put()
        return (user_prefs.user.nickname() if user_prefs.user else "default") + '|' + str(ctr)

    return db.run_in_transaction(txn)

def diceroll_order_key_gen(user_prefs):
    """
    Creates a unique string by using an increasing
    counter sharded per user.
    """

    def txn():
        user_prefs.count += 1
        user_prefs.put()
        return hashlib.md5(user_prefs.user.email() + "|" + str(user_prefs.count)).hexdigest()

    return db.run_in_transaction(txn)

def chat_order_key_gen(user_prefs):
#    user_prefs = get_user_prefs()

    def txn():
        user_prefs.chatCount += 1
        user_prefs.put()
        return hashlib.md5(user_prefs.user.email() + "|" + str(user_prefs.count)).hexdigest()

    return db.run_in_transaction(txn)

def get_user_prefs():
    if users.get_current_user():
        user_prefs = UserPrefs.get_or_insert(key_name='prefs-' + users.get_current_user().email())
    else:
        user_prefs = UserPrefs.get_or_insert(key_name='prefs-default')
#    user_prefs.last_access = datetime.now()
#    user_prefs.put() # update last access stamp
    return user_prefs

def get_prefs_for_user(user):
    return UserPrefs.get_or_insert(key_name = 'prefs-' + user.email())
