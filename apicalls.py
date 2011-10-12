import os
import sys

try:
  from urlparse import parse_qsl
except:
  from cgi import parse_qsl

import oauth2 as oauth
import twitter as identica

IdenticaError = identica.TwitterError

identica.REQUEST_TOKEN_URL = 'https://identi.ca/api/oauth/request_token?oauth_callback=oob'
identica.ACCESS_TOKEN_URL  = 'https://identi.ca/api/oauth/access_token'
identica.AUTHORIZATION_URL = 'https://identi.ca/api/oauth/authorize'
identica.SIGNIN_URL        = ''

class Authorization:
    """ Simplifies the OAuth authorization for identi.ca
    """
    def __init__(self,consumer_key,consumer_secret):
        self.oauth_consumer = oauth.Consumer(
                key=consumer_key, 
                secret=consumer_secret
            )
        self.request_token = None
    
    def get_authorization_url(self):
        """ Generates the authorization URL (with request token 
            parameter) to obtain the PIN for this application.
        """
        oauth_client = oauth.Client(self.oauth_consumer)
        resp, content = oauth_client.request(
                identica.REQUEST_TOKEN_URL, 
                'GET'
            )

        if resp['status'] != '200':
            raise IdenticaError(
                    'Invalid respond from Twitter requesting temp' + \
                    'token: %s (%s)' % (resp['status'], content)
                )
        else:
            self.request_token = dict(parse_qsl(content))
            return '%s?oauth_token=%s' % (
                    identica.AUTHORIZATION_URL, 
                    self.request_token['oauth_token']
                )
    
    def obtain_access_tokens(self,pincode):
        """ Obtains the access token for this application. The 
            ''pincode'' has to be obtained via get_authorization_url(),
            beforehand.
        """
        if self.request_token == None:
            raise Error(
                    'get_authorization_url() must be called first.'
                )
        token = oauth.Token(
                self.request_token['oauth_token'], 
                self.request_token['oauth_token_secret']
            )
        token.set_verifier(pincode)

        oauth_client  = oauth.Client(self.oauth_consumer, token)
        resp, content = oauth_client.request(
                identica.ACCESS_TOKEN_URL, 
                method='POST', 
                body='oauth_verifier=%s' % pincode
            )

        if resp['status'] != '200':
            raise  IdenticaError(
                    'The request for a Token did not succeed: %s (%s)' 
                        % (resp['status'], content)
                )
        else:
            return dict(parse_qsl(content))

class IdenticaApi(identica.Api):
    pass
