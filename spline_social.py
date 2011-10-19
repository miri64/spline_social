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

def main(argv):
    if len(argv) > 1:
        config_file = argv[1]
    else:
        config_file = CONFIG_FILE
    conf        = config.Config(config_file)
    irc_server  = conf.irc.server
    irc_port    = conf.irc.port
    irc_channel = conf.irc.channel
    
    rpc_port    = conf.rpc.port
    
    bot_nick        = conf.bot.bot_nick
    short_symbols   = conf.bot.short_symbols
    
    db_driver       = conf.db.driver
    db_username     = conf.db.username
    db_password     = conf.db.password
    db_name         = conf.db.database
    
    consumer_key = conf.identica.consumer_key
    consumer_secret = conf.identica.consumer_secret
    
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
    
    since_id = conf.identica.since_id
    
    db = DBConn(db_driver,db_username,db_password,db_name)
    
    api = apicalls.IdenticaApi(
            consumer_key = consumer_key,
            consumer_secret = consumer_secret,
            access_token_key = access_key,
            access_token_secret = access_secret,
            base_url = 'https://identi.ca/api'
        )
    
    rpc_server_thread = rpcs.initialize(rpc_port)
    
    bot = irc.TwitterBot(
            api, 
            irc_channel, 
            bot_nick, 
            irc_server, 
            irc_port,
            short_symbols,
            since_id
        )
    bot.start()

if __name__ == "__main__":
    main(sys.argv)
