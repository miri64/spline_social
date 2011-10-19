from SimpleXMLRPCServer import SimpleXMLRPCServer
import ldap
from db import User, Post
import config
from multiprocessing import Process

class SplineSocialAPI:
    def __init__(self, database, ldap_server, ldap_port = None):
        self.database = database
        if ldap_port == None:
            self.l = ldap.initialize('ldap://%s' % ldap_server)
        else:
            self.l = ldap.initialize('ldap://%s:%d' % (ldap_server, ldap_port))
        self.l.protocol_version = ldap.VERSION3
    
    def add_user(self, ldap_username, ldap_password, 
            irc_password, irc_username = None, gets_mail = False):
        (res, msg) = self.l.simple_bind_s(ldap_username, ldap_password)
        if res == 97:
            self.l.unbind_s()
            if irc_username != None:
                user = User(
                        user_id=irc_username,
                        password=irc_password,
                        ldap_id=ldap_username,
                        gets_mail=gets_mail
                    )
            else:
                user = User(
                        user_id=ldap_username,
                        password=irc_password,
                        ldap_id=ldap_username,
                        gets_mail=gets_mail
                    )
            self.database.add(user)
            return True
        else:
            return False

    def get_tweets(self, username = None):
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

def initialize(rpc_port, database, ldap_server, ldap_port):
    conf = config.Config()
    server = SimpleXMLRPCServer(('localhost', rpc_port))
    
    server.register_instance(SplineSocialAPI(database,ldap_server,ldap_port))
    p = Process(target=server.serve_forever)
    p.start()
    return p
