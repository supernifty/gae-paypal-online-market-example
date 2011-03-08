import decimal

from google.appengine.ext import db

class Profile(db.Model):
  '''extra user details'''
  owner = db.UserProperty()
  paypal_email = db.EmailProperty()  # for payment

  @staticmethod
  def from_user( u ):
    return Profile.all().filter( "owner = ", u ).get()

class Item(db.Model):
  '''an item for sale'''
  owner = db.UserProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  title = db.StringProperty()
  price = db.IntegerProperty() # cents
  image = db.BlobProperty()
  enabled = db.BooleanProperty()

  def price_dollars( self ):
    return self.price / 100.0

  def price_decimal( self ):
    return decimal.Decimal( str( self.price / 100.0 ) )

  @staticmethod
  def recent():
    return Item.all().filter( "enabled =", True ).order('-created').fetch(10)
 
class Purchase(db.Model):
  '''a completed transaction'''
  item = db.ReferenceProperty(Item)
  purchaser = db.UserProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  status = db.StringProperty( choices=( 'NEW', 'CREATED', 'ERROR', 'CANCELLED', 'RETURNED', 'COMPLETED' ) )
  status_detail = db.StringProperty()
  secret = db.StringProperty() # to verify return_url
  debug_request = db.TextProperty()
  debug_response = db.TextProperty()
