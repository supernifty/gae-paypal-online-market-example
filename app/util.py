import random
import string

from google.appengine.api import users

import model

def add_user( url, dict ):
  user = users.get_current_user()
  if user:
    dict['user'] = user
    dict['user_auth_url'] = users.create_logout_url( url )
    dict['paypal_email'] = paypal_email( user )
  else:
    dict['user_auth_url'] = users.create_login_url( url )

def paypal_email( user ):
  profile = model.Profile.from_user( user )
  if profile == None:
    return user.email() # no profile
  else:
    return profile.paypal_email

def random_alnum( count ):
  chars = string.letters + string.digits
  result = ''
  for i in range(count):
    result += random.choice(chars)
  return result

