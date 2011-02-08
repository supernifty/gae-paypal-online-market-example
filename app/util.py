from google.appengine.api import users

def add_user( url, dict ):
  user = users.get_current_user()
  if user:
    dict['user'] = user
    dict['user_auth_url'] = users.create_logout_url( url )
  else:
    dict['user_auth_url'] = users.create_login_url( url )

