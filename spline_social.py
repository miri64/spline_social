#! /usr/bin/env python

import apicalls, config, irc
import sys
import rpcs
from db import DBConn, User

CONFIG_FILE = ".spline_config"

def get_authorization(consumer_key, consumer_secret):
    """ Handles the authentication part.
    """
    auth = apicalls.Authorization(consumer_key, consumer_secret)
    authorization_url = auth.get_authorization_url()

    print 'Please visit this Identi.ca page and retrieve the pincode:'
    print '%s' % authorization_url

    pincode = raw_input('Pincode? ')

    return auth.obtain_access_tokens(pincode)

def get_access_token(conf, consumer_key, consumer_secret):
    if conf.identica.has_option('access_key') and \
            conf.identica.has_option('access_secret'):
        access_key = conf.identica.access_key
        access_secret = conf.identica.access_secret
    else:
        access_token = get_authorization(consumer_key, consumer_secret)
        access_key = access_token['oauth_token']
        access_secret = access_token['oauth_token_secret']
        conf.identica.access_key = access_key
        conf.identica.access_secret = access_secret
    return access_key, access_secret

def main(argv):
    if len(argv) > 1:
        config_file = argv[1]
    else:
        config_file = CONFIG_FILE
    conf        = config.Config(config_file)
    
    consumer_key = conf.identica.consumer_key
    consumer_secret = conf.identica.consumer_secret
    
    access_key, access_secret = get_access_token(
            conf, 
            consumer_key, 
            consumer_secret
        )
    
    db = DBConn(
            conf.db.driver,
            conf.db.database,
            conf.db.username,
            conf.db.password,
            conf.db.server,
            conf.db.port
        )
    
    api = apicalls.IdenticaApi(
            conf.bot.bot_nick,
            conf.smtp.server,
            consumer_key = consumer_key,
            consumer_secret = consumer_secret,
            access_token_key = access_key,
            access_token_secret = access_secret,
            base_url = 'https://identi.ca/api'
        )
    
    rpc_server_thread = rpcs.initialize(
            conf.rpc.port, 
            db, 
            conf.ldap.base,
            conf.ldap.server,
            conf.ldap.port
        )
    
    bot = irc.TwitterBot(
            api, 
            conf.irc.channel, 
            conf.irc.server, 
            conf.irc.port,
            conf.bot.bot_nick, 
            conf.bot.short_symbols,
            conf.bot.mention_interval,
            conf.bot.since_id
        )
    bot.start()

if __name__ == "__main__":
    main(sys.argv)
