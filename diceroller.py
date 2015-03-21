import os
import re
import random

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp.util import login_required

from rpghelper import default_values
from datamodel import DiceRoll
from datamodel import get_user_prefs
from datamodel import diceroll_order_key_gen
from pytz.gae import pytz
from datetime import datetime

class DiceRoller(webapp.RequestHandler):
    PAGESIZE = 20

    @login_required
    def get(self):
        self.post()

    def post(self):
        prefs = get_user_prefs()
        user_tz = pytz.timezone(prefs.timezone)
        bookmark = self.request.get("bookmark")
        prev = None
        if bookmark:
            rolls = DiceRoll.all().filter('campaign =', prefs.campaign).order('-order_key').filter('order_key <=',
                                                                                                   bookmark).fetch(
                    self.PAGESIZE + 1)
            prev_rolls = DiceRoll.all().filter('campaign =', prefs.campaign).order('order_key').filter('order_key >', bookmark).fetch(self.PAGESIZE)
            if len(prev_rolls) > 0:
                prev = prev_rolls[-1].order_key
        else:
            rolls = DiceRoll.all().filter('campaign =', prefs.campaign).order('-order_key').fetch(self.PAGESIZE + 1)
        next = None
        if len(rolls) == self.PAGESIZE + 1:
            next = rolls[-1].order_key
        rolls = rolls[:self.PAGESIZE]
        for roll in rolls:
            roll.stamp = roll.stamp.replace(tzinfo=pytz.utc).astimezone(user_tz)

        emsg = self.request.get('e')
        if emsg == '1':
            error_message = "Too many numbers!!! Can't throw more than 100d100's!"
        elif emsg == '2':
            error_message = 'Bad dice string, use something like "3d6+1".'
        else:
            error_message = None

        template_values = default_values(self.request.uri)
        template_values.update({
                                   'next': next,
                                   'prev': prev,
                                   'rolls': rolls,
                                   'error': error_message,
                                   })

        path = os.path.join(os.path.dirname(__file__), 'html', 'diceroller.html')
        self.response.out.write(template.render(path, template_values))

class RollDice(webapp.RequestHandler):
    def post(self):
        prefs = get_user_prefs()
        new_roll = roll_dice(self.request.get('description'),self.request.get('use'), prefs.campaign, prefs)
        if isinstance(new_roll,DiceRoll):
            new_roll.put()
            self.redirect('/dice')
        else:
            self.redirect('/dice?e=' + str(new_roll))

dicerollmatcherregexp = re.compile(r'^([0-9]+)(\.5)?[dD]([0-9]+)([+-][0-9]+)?$')

def roll_dice(description, use, campaign, user_prefs, parent = None):
    global dicerollmatcherregexp
    if parent:
        new_roll = DiceRoll(parent=parent)
    else:
        new_roll = DiceRoll()
    new_roll.use = use
    new_roll.description = description.expandtabs().replace(' ', '')
    new_roll.campaign = campaign
    m = dicerollmatcherregexp.match(new_roll.description)
    if m:
        new_roll.adder = int(m.group(4)) if m.lastindex == 4 else 0
        new_roll.half = m.group(2) is not None
        num_dice = int(m.group(1))
        die_faces = int(m.group(3))
        if num_dice <= 100 and die_faces <= 100:
            new_roll.die_faces = die_faces
            new_roll.rolls = [random.randint(1, die_faces) for _ in xrange(num_dice)]
            if new_roll.half:
                new_roll.rolls = new_roll.rolls + [random.randint(1, die_faces / 2)]
            new_roll.total = max(1, sum(new_roll.rolls, new_roll.adder))
            new_roll.order_key = datetime.now().isoformat() + "|" + diceroll_order_key_gen(user_prefs)
#            new_roll.put()
            return new_roll
        else:
            return 1
    else:
        return 2

application = webapp.WSGIApplication(
        [('/dice', DiceRoller),
         ('/dice/roll', RollDice)],
        debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
 
