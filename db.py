import os
from datetime import datetime, date, timedelta
import time
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
    
    class Banned(Exception):
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
    ldap_id = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
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
            if attr in ['banned', 'gets_mail']:
                if value in [0, None, False]:
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
    
    def add_post(self,status):
        self.posts.append(Post(status))
        self.session.commit()
        self.session.close()
    
    @staticmethod
    def get_by_user_id(user_id):
        db = DBConn()
        db_session = db.get_session()
        user = db_session.query(User). \
                filter(User.user_id == user_id).first()
        if user == None:
            db_session.close()
            return None
        user.session = db_session
        return user
    
    @staticmethod
    def get_by_irc_id(irc_id):
        db = DBConn()
        db_session = db.get_session()
        user = db_session.query(User). \
                select_from(sqlalchemy.orm.join(User, Login)). \
                filter(Login.irc_id == irc_id).first()
        if user == None:
            db_session.close()
            raise User.NotLoggedIn("You must identify to use this command.")
        user.session = db_session
        return user
    
    @staticmethod
    def get_by_ldap_id(ldap_id)
        db = DBConn()
        db_session = db.get_session()
        user = db_session.query(User). \
                filter(User.ldap_id == ldap_id).first()
        if user == None:
            db_session.close()
            return None
        user.session = db_session
        return user

class Post(Base):
    __tablename__ = 'posts'
    status_id = sqlalchemy.Column(
            sqlalchemy.Integer, 
            primary_key=True,
            unique=True
        )
    created_at = sqlalchemy.Column(
            sqlalchemy.DateTime, 
            nullable=False
        )
    poster_id = sqlalchemy.Column(
            sqlalchemy.String, 
            sqlalchemy.ForeignKey(
                    'users.user_id', 
                    onupdate="CASCADE", 
                    ondelete="CASCADE"
                ),
            nullable=False
        )
    deleted = sqlalchemy.Column(sqlalchemy.Boolean, default=False, nullable=False)
    deleter_id = sqlalchemy.Column(
            sqlalchemy.String, 
            sqlalchemy.ForeignKey(
                    'users.user_id', 
                    onupdate="CASCADE", 
                    ondelete="NO ACTION"
                ),
            default=None
        )
    
    user = sqlalchemy.orm.relationship(
            User, 
            backref=sqlalchemy.orm.backref('posts'),
            primaryjoin = User.user_id == poster_id
        )
    
    deleter = sqlalchemy.orm.relationship(
            User, 
            backref=sqlalchemy.orm.backref('deleted_posts'),
            primaryjoin = User.user_id == deleter_id
        )
    
    class DoesNotExist(Exception):
        def __init__(self, msg):
            self.msg = msg
        
        def __repr__(self):
            return self.msg
    
    def __init__(self, status, deleted = False, deleter = None):
        self.status_id = status.id
        t = time.localtime(
                int(status.created_at_in_seconds)
            )
        self.created_at = datetime(
                t.tm_year,t.tm_mon,t.tm_mday, 
                t.tm_hour, t.tm_min, t.tm_sec
            )
        self.deleted = deleted
        self.deleter = deleter
    
    def __repr__(self):
        return "<Post('%s')>" % self.status_id
    
    @staticmethod
    def get_all():
        db = DBConn()
        db_session = db.get_session()
        return db_session, db_session.query(Post). \
                filter(Post.deleted == False).all()
    
    @staticmethod
    def get_last(max = 10):
        db = DBConn()
        db_session = db.get_session()
        return db_session, db_session.query(Post). \
                filter(Post.deleted == False). \
                order_by("status_id DESC").limit(max). \
                from_self().order_by(Post.status_id).all()
    
    @staticmethod
    def get_by_user(user_id):
        db = DBConn()
        db_session = db.get_session()
        return db_session, db_session.query(Post). \
                select_from(sqlalchemy.orm.join(User, Post)). \
                filter(
                        User.ldap_id == user_id and 
                        Post.deleted == False
                    ).all()
    
    @staticmethod
    def get_by_day(datestring):
        date = date.strptime(datestring, "%Y-%m-%d")
        db_session = db.get_session()
        return db_session, db_session.query(Post). \
                filter(
                        Post.created_at.date == date and
                        Post.deleted == False
                    ).all()
    
    @staticmethod
    def mark_deleted(status_id, exception):
        try:
            if exception.args[0].find('Status deleted') < 0:
                return
        except AttributeError:
            return
        db = DBConn()
        db_session = db.get_session()
        post = db_session.query(Post). \
                filter(Post.status_id == status_id).first()
        if post != None:
            post.deleter_id = 'By API'
            post.deleted = True
            db_session.commit()
        else:
            raise Post.DoesNotExist("Post %d not tracked" % status_id)
        db_session.close()
    
    @staticmethod
    def delete(status_id, irc_id):
        db = DBConn()
        user = User.get_by_irc_id(irc_id)
        db_session = user.session:
            if not user.banned:
            post = db_session.query(Post). \
                    filter(Post.status_id == status_id).first()
            if post != None:
                post.deleter = user
                post.deleted = True
                db_session.commit()
            else:
                raise Post.DoesNotExist("Post %d not tracked" % status_id)
        else:
            raise User.Banned('You are banned.')
        db_session.close()

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
    
    def __init__(
            self, 
            driver = None, 
            name = None, 
            username = None, 
            password = None, 
            host = 'localhost',
            port = None
        ):
        if driver != None and name != None:
            if password == None:
                password = ''
            if username == None:
                authentication = ''
            else:
                authentication = '%s:%s' % (username,password)
            if host == None:
                host = 'localhost'
            elif port != None:
                host = '%s:%s' % (host,port)
            if driver.find('sqlite') < 0:
                self.engine = sqlalchemy.create_engine(
                        '%s://%s@%s/%s' % (driver,authentication,host,name)
                    )
            else:
                self.engine = sqlalchemy.create_engine(
                        '%s:///%s' % (driver,name)
                    )
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
