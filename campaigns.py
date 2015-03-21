import os

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp.util import login_required
from google.appengine.api import prospective_search

import datamodel
import rpghelper
from datamodel import Campaign

class Campaigns(webapp.RequestHandler):
    @login_required
    def get(self):
        prefs = datamodel.get_user_prefs()

        campaigns = Campaign.all().fetch(1000)
        
        emsg = self.request.get('e')  
        if emsg == '1':
            error_message = 'Please fill in both fields.'
        elif emsg == '2':
            error_message = 'You must be logged in!'
        else:
            error_message = None
            
        msg = self.request.get('m')
        if msg == '1':
            message = 'Campaign created successfully!'
        elif msg == '2':
            message = 'Campaign selected!'
        else:
            message = None
            
        if prefs.campaign:
            selected_campaign = prefs.campaign.key().id()
        else:
            selected_campaign = None
            
        template_values = rpghelper.default_values(self.request.uri)
        template_values.update({
            'campaigns': campaigns,
            'error': error_message,
            'message': message,
            'selected_campaign': selected_campaign 
            })

        path = os.path.join(os.path.dirname(__file__), 'html', 'campaigns.html')
        self.response.out.write(template.render(path, template_values))

class CreateCampaign(webapp.RequestHandler):
    def post(self):
        
        if not users.get_current_user():
            self.redirect('/campaigns?e=2')
        
        cname = self.request.get('name')
        ctype = self.request.get('type')
        
        if len(cname) < 3 or len(ctype) < 3:
            self.redirect('/campaigns?e=1')
        else:
            camp = Campaign()
            camp.name = cname
            camp.type = ctype
            camp.put()
            
            self.redirect('/campaigns?m=1')
            
class SelectCampaign(webapp.RequestHandler):
    def post(self):
        
        if not users.get_current_user():
            self.redirect('/campaigns?e=2')
            
        ckeyname = self.request.get('campaign')
        prefs = datamodel.get_user_prefs()
        if len(ckeyname) > 0:
            prefs.campaign = Campaign.get_by_id(int(ckeyname))
            datamodel.subscribe_to_campaign(prefs,prefs.campaign)
#            if prefs.campaign not in prefs.notification_campaigns:
#                prefs.notification_campaigns.append(prefs.campaign.key())
#            prospective_search.subscribe(datamodel.ChatMessageNotification,
#                                         'campaign_id == ' + ckeyname,
#                                         ckeyname)
        else:
            prefs.campaign = None
        prefs.put()
        
        self.redirect('/campaigns?m=2')
        
application = webapp.WSGIApplication(
    [('/campaigns', Campaigns),
     ('/campaigns/create', CreateCampaign),
     ('/campaigns/select', SelectCampaign)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
