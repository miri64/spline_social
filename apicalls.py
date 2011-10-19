import os
import sys
import smtplib
from email.mime.text import MIMEText

try:
  from urlparse import parse_qsl
except:
  from cgi import parse_qsl

from db import User, Post

import oauth2 as oauth
import twitter as identica

IdenticaError = identica.TwitterError

identica.REQUEST_TOKEN_URL = 'https://identi.ca/api/oauth/request_token?oauth_callback=oob'
identica.ACCESS_TOKEN_URL  = 'https://identi.ca/api/oauth/access_token'
identica.AUTHORIZATION_URL = 'https://identi.ca/api/oauth/authorize'
identica.SIGNIN_URL        = ''

information_text = """Hallo { ldap_id },
es wurde folgendes in deinem Namen gepostet.
"{ post_text }"
Solltest du dies nicht gepostet haben, loesche diesen Post (id = { post_id }) und aender dein Passwort.
Gruss,
{ bot_nick }
"""

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

def send_information_mail(bot_nick, user, post):
    user_mail = "%s@spline.inf.fu-berlin.de" % user.ldap_id
    bot_mail = "%s@spline.inf.fu-berlin.de" % 'spline'
    text = information_text.replace('{ ldap_id }', user.ldap_id)
    text = text.replace('{ post_text }', post.text)
    text = text.replace('{ post_id }', str(post.id))
    text = text.replace('{ bot_nick }', bot_nick)
    msg = MIMEText(text)
    
    msg['Subject'] = 'Dein Post von %s (ID %d)' % (post.created_at, post.id)
    msg['From'] = bot_mail
    msg['To'] = user_mail
    
    smtp = smtplib.SMTP('localhost')
    smtp.sendmail(bot_mail, [user_mail], msg.as_string())
    smtp.quit()

class IdenticaApi(identica.Api):
    def PostUpdate(self, bot_nick, source, *args, **kwargs):
        user = User.get_by_irc_id(source)
        status = super(IdenticaApi,self).PostUpdate(*args, **kwargs)
        if user.gets_mail:
            send_information_mail(bot_nick, user, status)
        user.add_post(status)
        return status
    
    def DestroyStatus(self, source, id, *args, **kwargs):
        Post.delete(id, source)
        return super(IdenticaApi,self).DestroyStatus(id, *args, **kwargs)
