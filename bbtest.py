import os

from google.appengine.dist import use_library
from rpghelper import default_values

use_library('django', '1.2')

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required, run_wsgi_app
from google.appengine.api import users

class BBTest(webapp.RequestHandler):
    @login_required
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'html', 'bb_test.html')
        template_values = default_values(self.request.uri)
        self.response.out.write(template.render(path, template_values))

class BBTest2(webapp.RequestHandler):
    @login_required
    def get(self):
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'

        self.response.out.write("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>BlackBerry Test</title>
</head>
<body>
<p><a href="%s">%s</a></p>
<h1>New test successful.</h1>
</body>
</html>
""" % (url,url_linktext))

class BBTest3(webapp.RequestHandler):
    def get(self):
        self.response.out.write("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>BlackBerry Test</title>
</head>
<body>
<h1>3rd test successful.</h1>
</body>
</html>
""")

class BBTest4(webapp.RequestHandler):
    @login_required
    def get(self):
        self.response.out.write("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>BlackBerry Test</title>
</head>
<body>
<h1>4th test successful.</h1>
</body>
</html>
""")

class BBTest5(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        self.response.out.write("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>BlackBerry Test</title>
</head>
<body>
<p><a href="%s">%s</a></p>
<h1>5th test successful.</h1>
</body>
</html>
""" % (url, url_linktext))

class BBTest6(webapp.RequestHandler):
        def get(self):
            self.response.out.write("""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>BlackBerry Test</title>
</head>
<body>
<h1>6th test successful.</h1>
</body>
</html>
""")


application = webapp.WSGIApplication(
        [('/bb_test', BBTest),
         ('/bb_test/2', BBTest2),
         ('/bb_test/4', BBTest4),
         ('/bb_test/5', BBTest5),
         ('/bb_test/6', BBTest6),
         ('/bb_test/3', BBTest3)],
        debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()