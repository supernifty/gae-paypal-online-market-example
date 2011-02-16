import cgi
import os
import random

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required
from google.appengine.ext.webapp.util import run_wsgi_app

import model
import paypal
import settings
import util

# hack to enable urllib to work with Python 2.6
import os
os.environ['foo_proxy'] = 'bar'
import urllib
urllib.getproxies_macosx_sysconf = lambda: {}

class Home(webapp.RequestHandler):
  def get(self):
    data = {
      'items': model.Item.recent(),
    }
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/main.htm')
    self.response.out.write(template.render(path, data))

class Sell(webapp.RequestHandler):
  def _process(self, message=None):
    data = { 
      'message': message,
      'items': model.Item.all().filter( 'owner =', users.get_current_user() ).fetch(100),
    }
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/sell.htm')
    self.response.out.write(template.render(path, data))

  @login_required
  def get(self, command=None):
    self._process()

  def post(self, command):
    user = users.get_current_user()
    if not user:
      self.redirect( users.create_login_url( "/sell" ) )
    else:
      if command == 'add':
        image = self.request.get("image")
        item = model.Item( owner=user, title=self.request.get("title"), price=long( float(self.request.get("price")) * 100 ), image=db.Blob(image), enabled=True )
        item.put()
        self._process("The item was added.")
      else:
        self._process("Unsupported command.")

class Buy(webapp.RequestHandler):
  @login_required
  def get(self, key):
    data = {
      'item': model.Item.get(key)
    }
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/buy.htm')
    self.response.out.write(template.render(path, data))

  def post(self, key):
    item = model.Item.get(key)
    # --- start purchase process ---
    purchase = model.Purchase( item=item, purchaser=users.get_current_user(), status='NEW', secret=util.random_alnum(16) )
    purchase.put()
    pay = paypal.Pay( item.price_dollars(), "%sreturn/%s/%s/" % (self.request.uri, purchase.key(), purchase.secret), "%scancel/%s/" % (self.request.uri, purchase.key()), self.request.remote_addr )

    purchase.debug_request = pay.raw_request
    purchase.debug_response = pay.raw_response
    purchase.put()
    
    if pay.status() == 'CREATED':
      purchase.status = 'CREATED'
      purchase.put()
      self.redirect( pay.next_url() ) # go to paypal
    else:
      purchase.status = 'ERROR'
      purchase.put()
      data = {
        'item': model.Item.get(key),
        'message': 'An error occurred during the purchase process'
      }
      util.add_user( self.request.uri, data )
      path = os.path.join(os.path.dirname(__file__), 'templates/buy.htm')
      self.response.out.write(template.render(path, data))

class BuyReturn(webapp.RequestHandler):
  def get(self, item_key, purchase_key, secret ):
    purchase = model.Purchase.get( purchase_key )
    # validation
    if purchase.status != 'CREATED':
      purchase.status = 'ERROR'
      purchase.status_detail = 'Expected status to be CREATED - duplicate transaction?'
      purchase.put
      self.error(501)

    elif secret != purchase.secret:
      purchase.status = 'ERROR'
      purchase.status_detail = 'BuyReturn secret "%s" did not match' % secret
      purchase.put
      self.error(501)

    else:
      purchase.status = 'RETURNED'
      purchase.put()
      # verify the transaction
  
      data = {
        'item': model.Item.get(item_key),
        'message': 'Purchased',
      }
      util.add_user( self.request.uri, data )
      path = os.path.join(os.path.dirname(__file__), 'templates/buy.htm')
      self.response.out.write(template.render(path, data))

class BuyCancel(webapp.RequestHandler):
  def get(self, item_key, purchase_key):
    purchase = model.Purchase.get( purchase_key )
    purchase.status = 'CANCELLED'
    purchase.put()
    data = {
      'item': model.Item.get(item_key),
      'message': 'Purchase cancelled',
    }
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/buy.htm')
    self.response.out.write(template.render(path, data))


class Image (webapp.RequestHandler):
    def get(self, id):
      item = db.get(id)
      if item.image:
          self.response.headers['Content-Type'] = "image/png"
          self.response.out.write(item.image)
      else:
          self.error(404)

application = webapp.WSGIApplication( [
    ('/', Home),
    ('/sell', Sell),
    ('/sell/(.*)/', Sell),
    ('/buy/(.*)/return/(.*)/(.*)/', BuyReturn),
    ('/buy/(.*)/cancel/(.*)/', BuyCancel),
    ('/buy/(.*)/', Buy),
    ('/image/(.*)/', Image),
  ],
  debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

