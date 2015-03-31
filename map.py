import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from django.utils import simplejson as json

import rpghelper


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
