import os
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base

from hashlib import sha256 as sha

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    user_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    banned = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    gets_mail = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    salt = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    
    def __init__(self, user_id, password, banned = False, gets_mail = False, salt = None):
        self.__dict__['db'] = DBConn()
        self.user_id = user_id
        if salt == None:
            self.salt = ''.join(map(lambda x:chr(range(128)[ord(x)%128]), os.urandom(255)))
        else:
            self.salt = salt
        self.password = (password,)
        self.banned = banned
        self.gets_mail = gets_mail
        
    def __setattr__(self, attr, value):
        if attr != 'password':
            if attr == 'banned' or attr == 'gets_mail':
                if value == 0 or value == None or value == False:
                    self.__dict__[attr] = False
                else:
                    self.__dict__[attr] = True
            else:
                self.__dict__[attr] = value
        else:
            if isinstance(value, str):
                self.__dict__[attr] = self._get_pwhash(value)
            else:
                self.__dict__[attr] = value[0]
    
    def __repr__(self):
        return "<User('%s','%s','%s','%s','%s')>" % \
                (self.user_id, self.password, str(self.banned),
                 str(self.gets_mail), self.salt)
    
    def _get_pwhash(self, password):
        hash = sha()
        hash.update(password)
        hash.update(self.salt)
        return hash.hexdigest()
    
    def validate_password(self,password):
        return self.password == self._get_pwhash(password)

class DBConn(object):
    def __new__(type, *args, **kwargs):
        if not '_the_instance' in type.__dict__:
            type._the_instance = object.__new__(type)
        return type._the_instance
    
    def __init__(self, name = None):
        if name != None:
            self.engine = sqlalchemy.create_engine('sqlite:///%s' % name)
            Base.metadata.create_all(self.engine)
    
    def get_session(self):
        Session = sqlalchemy.orm.sessionmaker(bind=self.engine)
        return Session()
