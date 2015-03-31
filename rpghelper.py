import os

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import datamodel

import pytz


def default_values(uri):
    if users.get_current_user():
        url = users.create_logout_url(uri)
        url_linktext = 'Logout'
    else:
        url = users.create_login_url(uri)
        url_linktext = 'Login'

    user_prefs = datamodel.get_user_prefs()

    return {'user_nick': user_prefs.nickname if user_prefs.nickname else (
    users.get_current_user().nickname() if users.get_current_user() else ''),
            'url': url,
            'url_linktext': url_linktext,
            'admin': users.is_current_user_admin(),
            'campaigns': datamodel.Campaign.all().fetch(100),
            'campaign': user_prefs.campaign,
            'current_timezone': user_prefs.timezone,
            'timezones': pytz.common_timezones_unfiltered}


class Admin(webapp.RequestHandler):
    def get(self):
        attrs_to_del = ['notification_campaigns', 'last_notification', 'use_dst', 'utc_offset']
        for user_prefs in datamodel.UserPrefs.all():
            for attr in attrs_to_del:
                if hasattr(user_prefs,attr):
                    delattr(user_prefs,attr)
            user_prefs.put()
        self.response.out.write('<html><body><a href="/">Back</a><br/>All done, really!</body></html>')


class SelectTimezone(webapp.RequestHandler):
    def post(self):
        timezone = self.request.get('timezone')
        prefs = datamodel.get_user_prefs()
        prefs.timezone = timezone
        prefs.put()
        self.redirect(self.request.headers["Referer"])


class SelectCampaign(webapp.RequestHandler):
    def post(self):
        if not users.get_current_user():
            self.redirect(self.request.headers["Referer"])

        ckeyname = self.request.get('campaign')
        prefs = datamodel.get_user_prefs()
        if len(ckeyname) > 0:
            prefs.campaign = datamodel.Campaign.get_by_id(int(ckeyname))
            datamodel.subscribe_to_campaign(prefs,prefs.campaign)
        else:
            prefs.campaign = None
        prefs.put()

        self.redirect(self.request.headers["Referer"])


class MainPage(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            campaign = datamodel.get_user_prefs().campaign
        else:
            campaign = None

        template_values = default_values(self.request.uri)
        template_values.update({'campaign': campaign})

        path = os.path.join(os.path.dirname(__file__), 'html', 'index.html')
        self.response.out.write(template.render(path, template_values))


class CookieTest(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<html><body>Cookie: " + self.request.cookies["test_cookie"] + "<br/>Val: " + self.request.get("val") + "</body></html>")

application = webapp.WSGIApplication(
        [('/', MainPage),
         ('/admin', Admin),
         ('/timezone', SelectTimezone),
         ('/cookie_test', CookieTest),
         ('/select_campaign', SelectCampaign)],
        debug=True)
