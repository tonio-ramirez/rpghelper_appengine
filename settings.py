import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp.util import login_required
from google.appengine.ext import db

from rpghelper import default_values
from datamodel import Campaign, CampaignSubscription
from datamodel import get_user_prefs


class Settings(webapp.RequestHandler):
    @login_required
    def get(self):
        prefs = get_user_prefs()
        msg = self.request.get('m')

        if msg == '1':
            message = 'Settings saved successfully!'
        else:
            message = None
        template_values = default_values(self.request.uri)
        campaigns = Campaign.all().fetch(100)
        selected_campaigns = [camp.campaign.key() for camp in CampaignSubscription.all().ancestor(prefs).filter('subscribed =', True)]
        template_values.update({
                                   'message': message,
                                   'user_campaigns': selected_campaigns,
                                   'campaigns': campaigns
                                   })
        path = os.path.join(os.path.dirname(__file__), 'html', 'settings.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        prefs = get_user_prefs()
        to_save = [prefs]
        #        selected_campaigns = [db.Key.from_path('Campaign', int(ckeyname)) for ckeyname in
#                              self.request.get_all('campaigns')]
        prefs.nickname = self.request.get('nickname')

        selected_campaigns = self.request.get_all('campaigns')
        #        prefs.notification_campaigns = selected_campaigns
        current_subscriptions = CampaignSubscription.all().ancestor(prefs)
        for subscription in current_subscriptions:
            ckeyname = str(subscription.campaign.key().id())
            subscription.subscribed = ckeyname in selected_campaigns
            to_save.append(subscription)
            if ckeyname in selected_campaigns:
                selected_campaigns.remove(ckeyname)
            #        db.delete(current_subscriptions)
        for ckeyname in selected_campaigns:
            subscription = CampaignSubscription(parent=prefs.key())
            subscription.campaign = Campaign.get_by_id(int(ckeyname))
            to_save.append(subscription)
        db.put(to_save)
        self.redirect('/settings?m=1')

application = webapp.WSGIApplication(
        [('/settings', Settings),
         ('/settings/save', Settings)],
        debug=True)

webapp.template.register_template_library('templatetags.smart_if')
