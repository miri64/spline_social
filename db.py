import os
from datetime import datetime, timedelta
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base

from hashlib import sha256 as sha

Base = declarative_base()

class User(Base):
    class NotLoggedIn(Exception):
        def __init__(self, msg):
            self.msg = msg
        
        def __repr__(self):
            return self.msg
    
    __tablename__ = 'users'
    user_id = sqlalchemy.Column(
            sqlalchemy.String, 
            primary_key=True, 
            unique=True
        )
    ldap_id = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    banned = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    gets_mail = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    salt = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    
    def __init__(self, user_id, ldap_id, password, banned = False, gets_mail = False, salt = None):
        self.__dict__['db'] = DBConn()
        self.user_id = user_id
        self.ldap_id = ldap_id
        if salt == None:
            self.salt = ''.join(map(lambda x:'./12345678890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'[ord(x)%65], os.urandom(64)))
            self.password = password
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
    
    def login(self,irc_id,password):
        if self.validate_password(password):
            db = DBConn()
            db_session = db.get_session()
            login = db_session.query(Login).filter(Login.irc_id == irc_id).first()
            if login == None:
                login = Login(irc_id,datetime.now()+timedelta(1))
                self.logins.append(login)
            else:
                login.expires = datetime.now()+timedelta(1)
            db_session.commit()
            db_session.close()
            self.session.commit()
            self.session.close()
            return True
        else:
            return False
    
    @staticmethod
    def get_by_user_id(user_id):
        db = DBConn()
        db_session = db.get_session()
        user = db_session.query(User). \
                filter(User.user_id == user_id).first()
        user.session = db_session
        return user

class Post(Base):
    __tablename__ = 'posts'
    status_id = sqlalchemy.Column(
            sqlalchemy.Integer, 
            primary_key=True,
            unique=True
        )
    user_id = sqlalchemy.Column(
            sqlalchemy.String, 
            sqlalchemy.ForeignKey(
                    'users.user_id', 
                    onupdate="CASCADE", 
                    ondelete="CASCADE"
                ),
            nullable=False
        )
    
    user = sqlalchemy.orm.relationship(
            User, 
            backref=sqlalchemy.orm.backref('posts')
        )
    
    def __init__(self, status):
        if isinstance(status,int):
            self.status_id = status
        else:
            self.status_id = status.id
    
    def __repr__(self):
        return "<Post('%s')>" % self.status_id

class Login(Base):
    __tablename__ = 'logins'
    
    irc_id = sqlalchemy.Column(
            sqlalchemy.String, 
            primary_key = True,
            unique = True
        )
    user_id = sqlalchemy.Column(
            sqlalchemy.String, 
            sqlalchemy.ForeignKey(
                    'users.user_id', 
                    onupdate="CASCADE", 
                    ondelete="CASCADE"
                ),
            nullable=False
        )
    expires = sqlalchemy.Column(
            sqlalchemy.DateTime,
            sqlalchemy.CheckConstraint("expires >= DATETIME('now')"), 
            primary_key = True,
            unique = True,
            nullable=False
        )
    
    user = sqlalchemy.orm.relationship(
            User, 
            backref=sqlalchemy.orm.backref('logins')
        )
    
    def __init__(self, irc_id, expires):
        self.irc_id = irc_id
        self.expires = expires
    
    def __repr__(self):
        return "<Post('%s','%s')>" % (self.irc_id, str(self.expires))

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
    
    def add(self, obj):
        db_session = self.get_session()
        db_session.add(obj)
        try:
            db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            pass
        finally:
            db_session.close()
    
    def get_query(self, type):
        db_session = self.get_session()
        query = db_session.query(type)
        db_session.close()
        return query