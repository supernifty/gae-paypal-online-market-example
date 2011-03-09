import decimal
import logging
import urllib
import urllib2

# hack to enable urllib to work with Python
import os
os.environ['foo_proxy'] = 'bar'

from django.utils import simplejson as json

import settings

class Pay( object ):
  def __init__( self, amount, return_url, cancel_url, remote_address, secondary_receiver=None, ipn_url=None ):
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
      'returnUrl': return_url,
      'cancelUrl': cancel_url,
      'requestEnvelope': { 'errorLanguage': 'en_US' },
    } 

    if secondary_receiver == None: # simple payment
      data['receiverList'] = { 'receiver': [ { 'email': settings.PAYPAL_EMAIL, 'amount': '%f' % amount } ] }
    else: # chained
      commission = amount * settings.PAYPAL_COMMISSION
      data['receiverList'] = { 'receiver': [ 
          { 'email': settings.PAYPAL_EMAIL, 'amount': '%f' % amount, 'primary': 'true' },
          { 'email': secondary_receiver, 'amount': '%f' % ( amount - commission ), 'primary': 'false' },
        ] 
      }

    if ipn_url != None:
      data['ipnNotificationUrl'] = ipn_url

    self.raw_request = json.dumps(data)
    request = urllib2.Request( "%s%s" % ( settings.PAYPAL_ENDPOINT, "Pay" ), data=self.raw_request, headers=headers )
    self.raw_response = urllib2.urlopen( request ).read() 
    self.response = json.loads( self.raw_response )
    
  def status( self ):
    if self.response.has_key( 'paymentExecStatus' ):
      return self.response['paymentExecStatus']
    else:
      return None 

  def amount( self ):
    return decimal.Decimal(self.results[ 'payment_gross' ])

  def paykey( self ):
    return self.response['payKey']

  def next_url( self ):
    return '%s?cmd=_ap-payment&paykey=%s' % ( settings.PAYPAL_PAYMENT_HOST, self.response['payKey'] )

class IPN( object ):
  def __init__( self, request ):
    # verify that the request is paypal's
    self.error = None
    verify_request = urllib2.Request( "%s?cmd=_notify-validate" % settings.PAYPAL_PAYMENT_HOST, data=urllib.urlencode( request.POST.copy() ) )
    verify_response = urllib2.urlopen( verify_request )
    # check code
    if verify_response.code != 200:
      self.error = 'PayPal response code was %i' % verify_response.code
      return
    # check response
    raw_response = verify_response.read()
    if raw_response != 'VERIFIED':
      self.error = 'PayPal response was "%s"' % raw_response
      return
    # check payment status
    if request.get('status') != 'COMPLETED':
      self.error = 'PayPal status was "%s"' % request.get('status')
      return

    (currency, amount) = request.get( "transaction[0].amount" ).split(' ')
    if currency != 'USD':
      self.error = 'Incorrect currency %s' % currency
      return

    self.amount = decimal.Decimal(amount)

  def success( self ):
    return self.error == None

