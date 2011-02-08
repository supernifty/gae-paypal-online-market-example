from google.appengine.ext import db

class Profile(db.Model):
  owner = db.UserProperty()
  paypal_email = db.EmailProperty()  # for payment

class Item(db.Model):
  '''an item for sale'''
  owner = db.UserProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  title = db.StringProperty()
  price = db.IntegerProperty() # cents
  image = db.BlobProperty()
  enabled = db.BooleanProperty()

  def price_dollars( self ):
    return self.price / 100

  @staticmethod
  def recent():
    return Item.all().filter( "enabled =", True ).order('-created').fetch(10)
 
class Purchase(db.Model):
  '''a completed transaction'''
  item = db.ReferenceProperty(Item)
  purchaser = db.UserProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  debug_request = db.StringProperty()
  debug_response = db.StringProperty()
  status = db.StringProperty( choices=( 'NEW', 'CREATED', 'ERROR', 'CANCELLED', 'RETURNED', 'COMPLETED' ) )