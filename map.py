import os

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp.util import login_required
from django.utils import simplejson as json

import datamodel
import rpghelper

from google.appengine.ext import db

class Map(webapp.RequestHandler):
    def get(self):
        template_values = rpghelper.default_values(self.request.uri)
        path = os.path.join(os.path.dirname(__file__), 'html', 'map2.html')
        self.response.out.write(template.render(path, template_values))

class Update(webapp.RequestHandler):
    def post(self):
        resp = json.dumps({'top': self.request.get('top'), 'left': self.request.get('left'), 'status': 'Saved'})
        self.response.out.write(resp)

application = webapp.WSGIApplication(
    [('/map', Map),
     ('/map/update', Update)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
