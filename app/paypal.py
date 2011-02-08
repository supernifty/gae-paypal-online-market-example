import urllib2

# TODO 2.6
import os
os.environ['foo_proxy'] = 'bar'

from django.utils import simplejson as json

import settings

class Pay( object ):
  def __init__( self, amount, return_url, cancel_url, remote_address ):
    headers = {
      'X-PAYPAL-SECURITY-USERID': settings.PAYPAL_USERID, 
      'X-PAYPAL-SECURITY-PASSWORD': settings.PAYPAL_PASSWORD, 
      'X-PAYPAL-SECURITY-SIGNATURE': settings.PAYPAL_SIGNATURE, 
      'X-PAYPAL-REQUEST-DATA-FORMAT': 'JSON',
      'X-PAYPAL-RESPONSE-DATA-FORMAT': 'JSON',
      'X-PAYPAL-APPLICATION-ID': settings.PAYPAL_APPLICATION_ID,
      'X-PAYPAL-DEVICE-IPADDRESS': remote_address,
    }

    data = {
      'actionType': 'PAY',
      'currencyCode': 'USD',
      'receiverList': { 'receiver': [ { 'email': settings.PAYPAL_EMAIL, 'amount': '%f' % amount } ] },
      'returnUrl': return_url,
      'cancelUrl': cancel_url,
      'requestEnvelope': { 'errorLanguage': 'en_US' },
    } 
    self.raw_request = json.dumps(data)
    request = urllib2.Request( "%s%s" % ( settings.PAYPAL_ENDPOINT, "Pay" ), data=self.raw_request, headers=headers )
    self.raw_response = urllib2.urlopen( request ).read() 
    self.response = json.loads( self.raw_response )
    
  def status( self ):
    return self.response['paymentExecStatus']

  def next_url( self ):
    return '%s?cmd=_ap-payment&paykey=%s' % ( settings.PAYPAL_PAYMENT_HOST, self.response['payKey'] )
