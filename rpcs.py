from SimpleXMLRPCServer import SimpleXMLRPCServer
import ldap
from db import DBConn, User, Post
import config
from multiprocessing import Process

def add_user(ldap_username, ldap_password, irc_password, irc_username = None, gets_mail = False):
    conf = config.Config()
    db = DBConn()
    if conf.ldap.port == None:
        l = ldap.initialize('ldap://%s' % conf.ldap.server)
    else:
        l = ldap.initialize('ldap://%s:%d' % (conf.ldap.server, conf.ldap.port))
    l.protocol_version = ldap.VERSION3
    (res, msg) = l.simple_bind_s(ldap_username, ldap_password)
    if res == 97:
        l.unbind_s()
        if irc_username != None:
            user = User(user_id=irc_username,password=irc_password,ldap_id=ldap_username,gets_mail=gets_mail)
        else:
            user = User(user_id=ldap_username,password=irc_password,ldap_id=ldap_username,gets_mail=gets_mail)
        db.add(user)
        return True
    else:
        return False

def get_tweets(username = None):
    if username == None:
        session, posts = Post.get_all()
    else:
        session, posts = Post.get_by_user(username)
    session.close()
    return map(
            lambda x: {
                'poster': User.get_by_user_id(x.poster_id).ldap_id, 
                'status_id': x.status_id
            }, 
            posts
        )

def initialize():
    conf = config.Config()
    server = SimpleXMLRPCServer(('localhost', conf.rpc.port))
    print conf.rpc.port
    server.register_function(add_user)
    server.register_function(get_tweets)
    p = Process(target=server.serve_forever)
    p.start()
    return p
