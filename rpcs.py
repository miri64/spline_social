from SimpleXMLRPCServer import SimpleXMLRPCServer
import ldap
from db import User, Post
import config
from multiprocessing import Process

class AuthenticationError(Exception):
    def __init__(self, msg):
        self.msg = msg
    
    def __repr__(self):
        return self.msg

class SplineSocialAPI:
    def __init__(self, database, ldap_base, ldap_server, ldap_port = None):
        self.database = database
        self.ldap_base = base
        if ldap_port == None:
            self.l = ldap.initialize('ldap://%s' % ldap_server)
        else:
            self.l = ldap.initialize('ldap://%s:%d' % (ldap_server, ldap_port))
        self.l.protocol_version = ldap.VERSION3
    
    def add_user(self, ldap_username, ldap_password, 
            irc_password, irc_username = None, gets_mail = False):
        ldap_dn = 'uid=%s,%s' % (ldap_username, self.ldap_base)
        (res, msg) = self.l.simple_bind_s(ldap_dn, ldap_password)
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
    
    def _get_and_validate_user(self, username, password):
        user = User.get_by_user_id(username)
        if user == None or not user.validate_password(password):
            raise AuthenticationError(
                    'Username or password does not match.'
                )
        return user
    
    def toggle_gets_mail(self, username, password):
        user = self._get_and_validate_user(username, password)
        user.gets_mail = not user.gets_mail
        user.session.commit()
        user.session.close()
        return user.gets_mail
    
    def set_new_password(self, username, password, new_password):
        user = self._get_and_validate_user(username, password)
        user.password = new_password
        user.session.commit()
        user.session.close()
    
    def get_user(self, username):
        user = User.get_by_user_id(username)
        user.session.close()
        return {
                'user_id': user.user_id,
                'ldap_id': user.ldap_id,
                'banned': user.banned,
                'gets_mail': user.gets_mail,
            }
    
    def get_tweets(self, username = None, limit = 20):
        if username == None:
            session, posts = Post.get_last(limit)
        else:
            session, posts = Post.get_by_user(username, limit)
        session.close()
        return map(
                lambda x: {
                    'poster': User.get_by_user_id(x.poster_id).ldap_id, 
                    'status_id': x.status_id
                }, 
                posts
            )

def initialize(rpc_port, database, ldap_base, ldap_server, ldap_port):
    conf = config.Config()
    server = SimpleXMLRPCServer(('localhost', rpc_port))
    
    server.register_instance(SplineSocialAPI(database,ldap_base,ldap_server,ldap_port))
    p = Process(target=server.serve_forever)
    p.start()
    return p
