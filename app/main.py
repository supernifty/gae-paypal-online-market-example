import cgi
import decimal
import logging
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
    seller_paypal_email = util.paypal_email(item.owner)
    if settings.USE_IPN:
      ipn_url = "%s/ipn/%s/%s/" % ( self.request.host_url, purchase.key(), purchase.secret )
    else:
      ipn_url = None
    pay = paypal.Pay( 
      item.price_dollars(), 
      "%sreturn/%s/%s/" % (self.request.uri, purchase.key(), purchase.secret), 
      "%scancel/%s/" % (self.request.uri, purchase.key()), 
      self.request.remote_addr,
      seller_paypal_email,
      ipn_url)

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
    '''user arrives here after purchase'''
    purchase = model.Purchase.get( purchase_key )

    # validation
    if purchase == None: # no key
      self.error(404)

    elif purchase.status != 'CREATED' and purchase.status != 'COMPLETED':
      purchase.status_detail = 'Expected status to be CREATED or COMPLETED, not %s - duplicate transaction?' % purchase.status
      purchase.status = 'ERROR'
      purchase.put()
      self.error(501)

    elif secret != purchase.secret:
      purchase.status = 'ERROR'
      purchase.status_detail = 'BuyReturn secret "%s" did not match' % secret
      purchase.put()
      self.error(501)

    else:
      if purchase.status != 'COMPLETED':
        purchase.status = 'RETURNED'
        purchase.put()

      # verify the transaction TODO
  
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

class Profile (webapp.RequestHandler):
  @login_required
  def get(self):
    data = {
      'profile': model.Profile.from_user(users.get_current_user())
    } 
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/profile.htm')
    self.response.out.write(template.render(path, data))

  def post(self):
    profile = model.Profile.from_user( users.get_current_user() )
    if profile == None:
      profile = model.Profile( owner = users.get_current_user() )
    profile.paypal_email = self.request.get('paypal_email')
    profile.put()
    data = { 
      'profile': profile, 
      'message': 'Profile updated' }
    util.add_user( self.request.uri, data )
    path = os.path.join(os.path.dirname(__file__), 'templates/profile.htm')
    self.response.out.write(template.render(path, data))

class IPN (webapp.RequestHandler):

  def post(self, key, secret):
    '''incoming post from paypal'''
    logging.debug( "IPN received for %s" % key )
    ipn = paypal.IPN( self.request )
    if ipn.success():
      # request is paypal's
      purchase = model.Purchase.get( key )
      if secret != purchase.secret:
        purchase.status = 'ERROR'
        purchase.status_detail = 'IPN secret "%s" did not match' % secret
        purchase.put()
      # confirm amount
      elif purchase.item.price_decimal() != ipn.amount:
        purchase.status = 'ERROR'
        purchase.status_detail = "IPN amounts didn't match. Item price %f. Payment made %f" % ( purchase.item.price_dollars(), ipn.amount )
        purchase.put()
      else:
        purchase.status = 'COMPLETED'
        purchase.put()
    else:
      logging.info( "PayPal IPN verify failed: %s" % ipn.error )
      logging.debug( "Request was: %s" % self.request.body )

application = webapp.WSGIApplication( [
    ('/', Home),
    ('/sell', Sell),
    ('/sell/(.*)/', Sell),
    ('/buy/(.*)/return/(.*)/(.*)/', BuyReturn),
    ('/buy/(.*)/cancel/(.*)/', BuyCancel),
    ('/buy/(.*)/', Buy),
    ('/image/(.*)/', Image),
    ('/profile', Profile),
    ('/ipn/(.*)/(.*)/', IPN),
  ],
  debug=True)

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

