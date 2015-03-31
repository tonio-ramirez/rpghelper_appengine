import cgi
import os
import re
import logging

from google.appengine.api import mail, users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required
from google.appengine.api.taskqueue import taskqueue
from google.appengine.api import xmpp
from google.appengine.api import channel
from google.appengine.api import prospective_search
from google.appengine.api.channel.channel import InvalidChannelClientIdError
from google.appengine.api import memcache
from google.appengine.ext import db

from rpghelper import default_values
from datamodel import ChatMessage, chat_order_key_gen, DiceRoll, UserPrefs, Campaign, OpenChannel
from datamodel import get_user_prefs
from diceroller import roll_dice
from datetime import datetime, timedelta
import datamodel
import myjson as json


class Chat(webapp.RequestHandler):
    @login_required
    def get(self):
        prefs = get_user_prefs()
        if self.request.get('campaign'):
            ckeyname = self.request.get('campaign')
            prefs.campaign = Campaign.get_by_id(int(ckeyname))
            datamodel.subscribe_to_campaign(user_prefs=prefs,campaign=prefs.campaign)
            prefs.put()
            self.redirect('/chat')
        else:
            prefs.last_access = datetime.now()
            prefs.put()
            template_values = default_values(self.request.uri)

            if prefs.campaign is None:
                campaign_name = None
                campaign_type = None
            else:
                campaign_name = prefs.campaign.name
                campaign_type = prefs.campaign.type

            template_values.update({
                                       'campaign_type': campaign_type,
                                       'campaign_name': campaign_name,
                                       'current_user': users.get_current_user().nickname()
                                       })
            path = os.path.join(os.path.dirname(p=__file__), 'html', 'chat.html')
            self.response.out.write(template.render(path, template_values))

class ChatMessages(webapp.RequestHandler):
    PAGESIZE = 10

    def get(self):
        prefs = get_user_prefs()
        bookmark = self.request.get("bookmark")

        prev = None

        if bookmark:
            chat_messages = ChatMessage.all().filter('campaign =', prefs.campaign).order('-order_key').filter(
                    'order_key <=',
                    bookmark).fetch(
                    self.PAGESIZE + 1)
            prev_chats = ChatMessage.all().filter('campaign =', prefs.campaign).order('order_key').filter('order_key >',
                                                                                                          bookmark).fetch(
                    self.PAGESIZE)
            if len(prev_chats) > 0:
                prev = prev_chats[-1].order_key
        else:
            chat_messages = ChatMessage.all().filter('campaign =', prefs.campaign).order('-order_key').fetch(
                    self.PAGESIZE + 1)
        next = None
        if len(chat_messages) == self.PAGESIZE + 1:
            next = chat_messages[-1].order_key
        chat_messages = chat_messages[:self.PAGESIZE]
        all_rolls = []
        for chat_message in chat_messages:
            rolls = DiceRoll.all().ancestor(chat_message)
            all_rolls.append(sorted(rolls,key=lambda x: x.match_start))

        # update latest read message for current campaign
        if prefs.latest_read_message_by_campaign is None:
            prefs.latest_read_message_by_campaign = {}
        if prefs.campaign and len(chat_messages) > 0 and\
           (not prefs.latest_read_message_by_campaign.has_key(prefs.campaign.key().id()) or
            prefs.latest_read_message_by_campaign[prefs.campaign.key().id()] < chat_messages[0].order_key):
            prefs.latest_read_message_by_campaign[prefs.campaign.key().id()] = chat_messages[0].order_key
        prefs.last_access = datetime.now()
        prefs.put()

        resp = {
            "prev": prev,
            "next": next,
            "messages": chat_messages,
            "all_rolls": all_rolls
        }
        self.response.out.write(json.dumps(input=resp))

max_min_regexp = re.compile(
        r'\[<span class="chatroll">(?P<total>\d+)</span> \(<span class="chatrolldetail">(?P<number>\d+)(?P<half>\.5)?d(?P<faces>\d+)(?P<adder>(?:\+|-)\d+)?:')

dice_roll_regexp = re.compile(r'\[[^][]+\]')

class PostMessage(webapp.RequestHandler):
    def post(self):
        if not self.request.get('message'):
            self.response.out.write(json.dumps(input={'success':False}))
        else:
            global max_min_regexp
            global dice_roll_regexp

            prefs = get_user_prefs()

            msg = ChatMessage()
            msg.campaign = prefs.campaign
            msg.message = cgi.escape(self.request.get('message')).encode('ascii', 'xmlcharrefreplace').replace('\n',
                                                                                                               '<br/>')
            msg.order_key = datetime.now().isoformat() + "|" + chat_order_key_gen(prefs)
            msg.put()

            rolls = []

            for match in dice_roll_regexp.finditer(msg.message):
                roll = roll_dice(match.group(0)[1:-1], 'see chat', msg.campaign, prefs, parent=msg)
                if isinstance(roll, DiceRoll):
                    roll.match_start = match.start()
                    roll.match_end = match.end()
                    rolls.append(roll)

            db.put(rolls)

            subs = prospective_search.list_subscriptions(datamodel.ChatMessageNotification)
            logging.info('State: OK: ' + str(prospective_search.SubscriptionState.OK))
            logging.info('State: PENDING: ' + str(prospective_search.SubscriptionState.PENDING))
            logging.info('State: ERROR: ' + str(prospective_search.SubscriptionState.ERROR))
            for sub in subs:
                logging.info('Subscription: ' +sub[0] + ', query: '+sub[1] + ', state: ' + str(sub[3]))

            notification = datamodel.ChatMessageNotification()
            notification.campaign_id = msg.campaign.key().id()
            notification.user_nick = msg.user.nickname()

            taskqueue.add(url='/chat/notify_client',
                          params={'campaign': msg.campaign.key().id(), 'user': users.get_current_user().nickname()},
                          method='GET',
                          queue_name='client-notification')

            if memcache.add('notification_queued', True, time=15):
                taskqueue.add(url='/chat/send_notifications',
                              method='GET',
                              queue_name='client-notification',
                              countdown=15)

            self.response.out.write(json.dumps(input={'success':True}))


class NotifyClient(webapp.RequestHandler):
    def get(self):
        campaign = Campaign.get_by_id(int(self.request.get('campaign')))
        open_channels = OpenChannel.all().filter('campaign =', campaign)
        now = datetime.now()
        total = 0
        expired = 0
        for open_channel in open_channels:
            total += 1
            if open_channel.expiration < now or not open_channel.clientId:
                expired += 1
                open_channel.delete()
            else:
                try:
                    channel.send_message(client_id=open_channel.clientId, message=json.dumps(
                                input={"new_messages": True, "from": self.request.get('user')}))
                except InvalidChannelClientIdError:
                    expired += 1
                    open_channel.delete()
        logging.info('Total channels: ' + str(total) + ', expired: ' + str(expired))

    def post(self):
        notification = prospective_search.get_document(request=self.request)
        logging.info('Got a message from: ' + notification.user_nick + ' in: ' + str(notification.campaign_id))
        open_channels = OpenChannel.all().filter('campaign =',Campaign.get_by_id(int(notification.campaign_id)))
        now = datetime.now()
        total = 0
        expired = 0
        for open_channel in open_channels:
            total += 1
            if open_channel.expiration < now or not open_channel.clientId:
                expired += 1
                open_channel.delete()
            else:
                try:
                    channel.send_message(client_id=open_channel.clientId, message=json.dumps(input={"new_messages":True, "from":notification.user_nick}))
                except InvalidChannelClientIdError:
                    expired += 1
                    open_channel.delete()
        logging.info('Total channels: ' + str(total) + ', expired: ' + str(expired))


def calc_max(number, half, faces, adder):
    tmp = number * faces + adder
    if half:
        tmp += faces / 2
    return max(tmp, 1)


def calc_min(number, half, adder):
    return max(number + (1 if half else 0) + adder, 1)


class Notify(webapp.RequestHandler):
    NOTIFICATION_SUBJECT = 'New message'

    NOTIFICATION_MESSAGE = """
There are new chat messages in the %s campaign!

http://rpghelper.appspot.com/chat?campaign=%s

(Do not reply to this message.)
"""

    XMPP_NOTIFICATION_MESSAGE = """
There are new chat messages in the %s campaign!

http://rpghelper.appspot.com/chat?campaign=%s
"""
    NOTIFICATION_EMAIL_ADDRESS = 'RPG Helper <notifications@rpghelper.appspotmail.com>'

    def post(self):
        recipients = self.request.get_all('recipients')

        original_recipients = ', '.join(recipients)
        ckeyname = self.request.get('campaign')
        campaign = Campaign.get_by_id(int(ckeyname))
        presences = map(xmpp.get_presence,recipients)
        recipients = zip(recipients,presences)
        xmpp_recipients = filter(None,map(lambda r: r[0] if r[1] else None,recipients))
        email_recipients = filter(None, map(lambda r: r[0] if not r[1] else None, recipients))
        if xmpp_recipients:
            status_codes = xmpp.send_message(xmpp_recipients,self.XMPP_NOTIFICATION_MESSAGE % (campaign.name,campaign.key().id()))
            email_recipients += filter(None,map(lambda r, c: r if c != xmpp.NO_ERROR else None, xmpp_recipients,status_codes))
        else:
            status_codes = []
        info = """
Recipients:       %s
XMPP Recipients:  %s
Return codes:     %s
Email recipients: %s
""" % (original_recipients,', '.join(xmpp_recipients),', '.join(map(xmpp.xmpp_service_pb.XmppMessageResponse.XmppMessageStatus_Name,status_codes)),', '.join(email_recipients))
        logging.debug(info)
        if email_recipients:
            mail.send_mail(self.NOTIFICATION_EMAIL_ADDRESS, email_recipients, self.NOTIFICATION_SUBJECT,
                           self.NOTIFICATION_MESSAGE % (campaign.name,campaign.key().id()))


class Check(webapp.RequestHandler):
    def get(self):
        prefs = get_user_prefs()
        self.response.headers['Cache-Control'] = 'no-cache'
        if prefs.campaign:
            last_chat = ChatMessage.all().filter('campaign = ', prefs.campaign).order('-order_key').get()
            logging.info('curr: ' + str(last_chat.stamp))
            put = False
            if prefs.latest_read_message_by_campaign is None:
                prefs.latest_read_message_by_campaign = {}
                put = True
            if not prefs.latest_read_message_by_campaign.has_key(prefs.campaign.key().id()) or \
                prefs.latest_read_message_by_campaign[prefs.campaign.key().id()] < last_chat.order_key:
                self.response.out.write('yes')
                prefs.latest_read_message_by_campaign[prefs.campaign.key().id()] = last_chat.order_key
                put = True
            else:
                self.response.out.write('no')
            if put:
                prefs.put()
        else:
            self.response.out.write('no')


class CheckAndSendNotification(webapp.RequestHandler):
    def get(self):
        memcache.delete('notification_queued')
        campaigns = Campaign.all()
        for campaign in campaigns:
            recipients = []
            last_message = ChatMessage.all().filter('campaign =', campaign).order('-order_key').get()
            if last_message:
                user_prefs = [subs.parent() for subs in datamodel.CampaignSubscription.all().filter('campaign =', campaign).filter('subscribed =', True)]
                to_save = []
                for user_pref in user_prefs:
                    if user_pref.user:
                        put = False
                        if user_pref.last_notification_by_campaign is None:
                            user_pref.last_notification_by_campaign = {}
                            put = True
                        if user_pref.latest_read_message_by_campaign is None:
                            user_pref.latest_read_message_by_campaign = {}
                            put = True

                        has_unread = not user_pref.latest_read_message_by_campaign.has_key(campaign.key().id()) or \
                            user_pref.latest_read_message_by_campaign[campaign.key().id()] < last_message.order_key
                        email_sent = user_pref.last_notification_by_campaign.has_key(campaign.key().id()) and \
                            (not user_pref.last_access or user_pref.last_notification_by_campaign[campaign.key().id()] > user_pref.last_access)
                        if has_unread and not email_sent:
                            recipients.append(user_pref.user.email())
                            user_pref.latest_read_message_by_campaign[campaign.key().id()] = last_message.order_key
                            user_pref.last_notification_by_campaign[campaign.key().id()] = datetime.now()
                            put = True
                        if put:
                            to_save.append(user_pref)
                db.put(to_save)
                if recipients:
                    taskqueue.add(url='/chat/notify',
                                  params={'recipients': recipients, 'campaign': campaign.key().id()},
                                  method='POST',
                                  queue_name='external-notification')


class NewToken(webapp.RequestHandler):
    @login_required
    def get(self):
        logging.info('New token requested.')
        campaign_id = self.request.get('campaign')
        if campaign_id:
            campaign = Campaign.get_by_id(int(campaign_id))
            if campaign:
                current_client_id = self.request.cookies["client_id"] if self.request.cookies.has_key(
                        "client_id") else None
                if current_client_id:
                    client_id = current_client_id
                    chn = OpenChannel.all().filter('clientId =', current_client_id).get()
                else:
                    client_id = datamodel.generate_client_id(user_prefs=get_user_prefs())
                    chn = None
                if not chn:
                    chn = OpenChannel()
                    chn.clientId = current_client_id
                chn.campaign = campaign
                chn.clientId = client_id
                chn.expiration = datetime.now() + timedelta(hours=2)
                chn.put()
                token = channel.create_channel(client_id=client_id)
                logging.info('New token created for ' + client_id)
                self.response.out.write(json.dumps(input={"new_token":token, "client_id":client_id}))
            else:
                self.response.out.write(json.dumps(input={"error":"Campaign not found"}))
        else:
            self.response.out.write(json.dumps(input={"error":"Campaign ID not sent!"}))


class ValidateClientId(webapp.RequestHandler):
    def get(self):
        client_id = self.request.cookies["client_id"] if self.request.cookies.has_key("client_id") else None
        if client_id:
            open_channels = OpenChannel.all().filter('clientId =', client_id)
            logging.info("Validating client id: " + client_id)
            if open_channels.count(1) > 0:
                logging.debug('Client ID is valid.')
                campaign = Campaign.get_by_id(int(self.request.get('campaign')))
                logging.debug('For campaign: ' + campaign.name)
                for open_channel in open_channels:
                    open_channel.campaign = campaign
                    open_channel.put()
                self.response.out.write(json.dumps(input={'valid': True}))
            else:
                logging.debug('Client ID is invalid.')
                self.response.out.write(json.dumps(input={'valid': False}))
        else:
            logging.debug('No Client ID cookie sent.')
            self.response.out.write(json.dumps(input={'valid': False}))


application = webapp.WSGIApplication(
        [('/chat', Chat),
         ('/chat/load_messages', ChatMessages),
         ('/chat/post', PostMessage),
         ('/chat/check', Check),
         ('/chat/new_token', NewToken),
         ('/chat/validate_client_id', ValidateClientId),
         ('/chat/notify', Notify),
         ('/chat/notify_client', NotifyClient),
         ('/chat/send_notifications', CheckAndSendNotification)],
        debug=True)
