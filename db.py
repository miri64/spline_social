import os
from datetime import datetime, date, timedelta
from irclib import nm_to_n
import time
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from multiprocessing import current_process

from hashlib import sha256 as sha

Base = declarative_base()

IntegrityError = sqlalchemy.exc.IntegrityError
FlushError = sqlalchemy.exc.FlushError

class User(Base):
    class NotLoggedIn(Exception):
        def __init__(self, msg):
            self.msg = msg
        
        def __repr__(self):
            return self.msg
        
        def __str__(self):
            return repr(self)
    
    class NoRights(Exception):
        def __init__(self, msg):
            self.msg = msg
        
        def __repr__(self):
            return self.msg
        
        def __str__(self):
            return repr(self)
    
    class EmptyPasswordException:
        def __init__(self, msg):
            self.msg = msg
        
        def __repr__(self):
            return self.msg
        
        def __str__(self):
            return repr(self)
    
    __tablename__ = 'users'
    user_id = sqlalchemy.Column(
            sqlalchemy.String, 
            primary_key=True, 
            unique=True,
            nullable=False
        )
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    admin = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    banned = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    gets_mail = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)
    salt = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    
    def __init__(self, user_id, password, admin = False, 
            banned = False, gets_mail = False, salt = None):
        if user_id == None:
            raise ValueError("'user_id' may not be None.")
        if password == None or password == '':
            raise ValueError("'password' may not be None or empty.")
        db_session = DBConn.get_db_session()
        self.__dict__['user_id'] = user_id
        if salt == None:
            self.__dict__['salt'] = ''.join(
                    map(
                            lambda x:('./12345678890ABCDE' + 
                                    'FGHIJKLMNOPQRSTUVWX' + 
                                    'YZabcdefghijklmnopq' + 
                                    'rstuvwxyz')[ord(x)%65], 
                            os.urandom(64)
                        )
                )
            self.__dict__['password'] = self._get_pwhash(password)
        else:
            self.__dict__['salt'] = salt
            self.__dict__['password'] = password
        users = db_session.query(User).first()
        if users == None:
            admin = True
        self.__dict__['admin'] = admin
        self.__dict__['banned'] = banned
        self.__dict__['gets_mail'] = gets_mail
        DBConn().add(self)
        
    def __setattr__(self, attr, value):
        if attr != 'password':
            if attr in ['banned', 'gets_mail', 'admin']:
                if value in [0, None, False, '']:
                    super(User, self).__setattr__(attr, False)
                else:
                    super(User, self).__setattr__(attr, True)
            else:
                super(User, self).__setattr__(attr, value)
        else:
            super(User, self).__setattr__(attr, self._get_pwhash(value))
        if attr != '_sa_instance_state':
            db_session = DBConn.get_db_session()
            try:
                db_session.commit()
            except IntegrityError, e:
                db_session.rollback()
                raise e
    
    def __repr__(self):
        return "<User('%s','%s','%s','%s','%s')>" % \
                (self.user_id, self.password, str(self.banned),
                 str(self.gets_mail), self.salt)
    
    def _get_pwhash(self, password):
        hash = sha()
        if password != None and password != '':
            hash.update(password)
        else:
            raise User.EmptyPasswordException(
                    'Your password is None or an empty string: '+
                    repr(password)
                )
        hash.update(self.salt)
        return hash.hexdigest()
    
    def validate_password(self,password):
        return self.password == self._get_pwhash(password)
    
    def login(self,irc_id,password):
        if self.validate_password(password):
            db_session = DBConn.get_db_session()
            login = Login.get(irc_id)
            if login == None:
                login = Login(irc_id,datetime.now()+timedelta(1))
                self.logins.append(login)
            else:
                login.update()
            db_session.commit()
            return True
        else:
            return False
    
    def update_login(self,irc_id):
        login = Login.get(irc_id)
        if login != None:
            login.update()
    
    def add_post(self,status,irc_id = None):
        if status == None:
            raise ValueError("'status' may not be None.")
        db_session = DBConn.get_db_session()
        if irc_id != None:
            self.update_login(irc_id)
        post = Post(status)
        self.posts.append(post)
        db_session.commit()
        return post
    
    @staticmethod
    def get_by_user_id(user_id):
        if user_id == None:
            raise ValueError("'user_id' may not be None.")
        db_session = DBConn.get_db_session()
        user = db_session.query(User). \
                filter(User.user_id == user_id).first()
        return user
    
    @staticmethod
    def get_by_irc_id(irc_id):
        if irc_id == None:
            raise ValueError("'irc_id' may not be None.")
        db_session = DBConn.get_db_session()
        login = Login.get(irc_id)
        if login == None:
            raise User.NotLoggedIn("IRC-User '%s' not logged in." % nm_to_n(irc_id))
        return login.user
    
    @staticmethod
    def delete(user):
        if user == None:
            raise ValueError("'user' may not be None.")
        if not isinstance(user, User):
            user = db_session.query(User). \
                    filter(User.user_id == str(user)).first()
        db_session = DBConn.get_db_session()
        db_session.delete(user)
        db_session.commit()

class Post(Base):
    __tablename__ = 'posts'
    status_id = sqlalchemy.Column(
            sqlalchemy.Integer, 
            primary_key=True,
            unique=True,
            nullable=False
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
        
        def __str__(self):
            return repr(self)
    
    def __init__(self, status, deleted = False, deleter = None):
        self.__dict__['status_id'] = status.id
        if status.created_at_in_seconds == None:
            raise ValueError("'created_at' may not be None.")
        if status.id == None:
            raise ValueError("'status_id' may not be None.")
        self.__dict__['created_at'] = datetime.fromtimestamp(
                int(status.created_at_in_seconds)
            )
        self.__dict__['deleted'] = deleted
        self.__dict__['deleter'] = deleter
    
    def __repr__(self):
        return "<Post('%s')>" % self.status_id
    
    def __setattr__(self, attr, value):
        db_session = DBConn.get_db_session()
        if attr == 'deleted':
            if value in [0, None, False, '']:
                value = False
            else:
                value = True
        super(Post, self).__setattr__(attr, value)
        if attr != '_sa_instance_state':
            try:
                db_session.commit()
            except IntegrityError, e:
                db_session.rollback()
                raise e
    
    @staticmethod
    def get(status_id):
        if status_id == None:
            raise ValueError("'status_id' may not be None.")
        db_session = DBConn.get_db_session()
        return db_session.query(Post). \
                filter(Post.status_id == status_id).first()
    
    @staticmethod
    def get_all():
        db_session = DBConn.get_db_session()
        return db_session.query(Post). \
                filter(Post.deleted == False).all()
    
    @staticmethod
    def get_last(max = 10):
        if max < 0:
            raise ValueError("'max' may not be negative.")
        db_session = DBConn.get_db_session()
        return db_session.query(Post). \
                filter(Post.deleted == False). \
                order_by("status_id DESC").limit(max). \
                from_self().order_by(Post.status_id).all()
    
    @staticmethod
    def get_by_user_id(user_id, max = 10):
        if user_id == None:
            raise ValueError("'user_id' may not be None.")
        if max < 0:
            raise ValueError("'max' may not be negative.")
        db_session = DBConn.get_db_session()
        return db_session.query(Post). \
                join(Post.user). \
                filter(
                        User.user_id == user_id and 
                        Post.deleted == False
                    ).limit(max).all()
    
    @staticmethod
    def get_by_day(datestring):
        if datestring == None:
            raise ValueError("'datestring' may not be None.")
        day = datetime.strptime(datestring, "%Y-%m-%d")
        db_session = DBConn.get_db_session()
        return db_session.query(Post). \
                filter(
                        sqlalchemy.and_([
                            Post.created_at >= day,
                            Post.created_at < day + timedelta(days=1),
                        ]) and
                        Post.deleted == False
                    ).all()
    
    @staticmethod
    def mark_deleted(status_id, exception):
        if status_id == None:
            raise ValueError("'status_id' may not be None.")
        if exception == None:
            raise ValueError("'exception' may not be None.")
        try:
            if exception.args[0].find('Status deleted') < 0:
                raise ValueError("First argument of 'exception' must contain 'Status deleted'.")
        except AttributeError:
            raise ValueError("First argument of 'exception' must contain 'Status deleted'.")
        db_session = DBConn.get_db_session()
        post = db_session.query(Post). \
                filter(Post.status_id == status_id).first()
        if post != None:
            post.deleter_id = 'By API'
            post.deleted = True
        else:
            raise Post.DoesNotExist("Post %d not tracked" % status_id)
    
    @staticmethod
    def delete(status_id, irc_id):
        if status_id == None:
            raise ValueError("'status_id' may not be None.")
        if irc_id == None:
            raise ValueError("'irc_id' may not be None.")
        db_session = DBConn.get_db_session()
        user = User.get_by_irc_id(irc_id)
        if not user.banned:
            post = db_session.query(Post). \
                    filter(Post.status_id == status_id).first()
            if post != None:
                post.deleter = user
                post.deleted = True
            else:
                raise Post.DoesNotExist("Post %d not tracked" % status_id)
        else:
            raise User.NoRights('You are banned.')

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
            nullable=False
        )
    
    user = sqlalchemy.orm.relationship(
            User, 
            backref=sqlalchemy.orm.backref('logins')
        )
    
    def __init__(self, irc_id, expires):
        if irc_id == None:
            raise ValueError("'irc_id' may not be None.")
        if expires == None:
            raise ValueError("'expires' may not be None.")
        self.__dict__['irc_id'] = irc_id
        self.__dict__['expires'] = expires
    
    def __repr__(self):
        return "<Post('%s','%s')>" % (self.irc_id, str(self.expires))
    
    def __setattr__(self, attr, value):
        if attr == 'expires':
            raise AttributeError("'expires' can't be set. Use update to set it to tomorrow.")
        db_session = DBConn.get_db_session()
        super(Login,self).__setattr__(attr, value)
        if attr != '_sa_instance_state':
            try:
                db_session.commit()
            except IntegrityError, e:
                db_session.rollback()
                raise e
    
    def update(self):
        super(Login,self).__setattr__('expires', datetime.now()+timedelta(1))
    
    @staticmethod
    def get(irc_id):
        if irc_id == None:
            raise ValueError("'irc_id' may not be None.")
        db_session = DBConn.get_db_session()
        db_session.query(Login). \
                filter(Login.expires <= datetime.now()). \
                delete()
        return db_session.query(Login). \
                filter(Login.irc_id == irc_id).first()

class Timeline(Base):
    __tablename__ = 'timelines'
    
    name = sqlalchemy.Column(
            sqlalchemy.String, 
            primary_key = True,
            unique = True,
            nullable=False
        )
    since_id = sqlalchemy.Column(
            sqlalchemy.Integer, 
            nullable=False
        )
    
    def __init__(self, name, since_id):
        if name == None:
            raise ValueError("'name' may not be None.")
        if since_id == None:
            raise ValueError("'since_id' may not be None.")
        self.name = name.strip()
        self.since_id = since_id
        DBConn().add(self)
    
    def __repr__(self):
        return "<Timeline('%s','%d')>" % (self.name, self.since_id)
    
    def __setattr__(self, attr, value):
        db_session = DBConn.get_db_session()
        super(Timeline, self).__setattr__(attr, value)
        if attr != '_sa_instance_state':
            try:
                db_session.commit()
            except IntegrityError, e:
                db_session.rollback()
                raise e
    
    @staticmethod
    def get_by_name(name):
        if name == None:
            raise ValueError("'name' may not be None.")
        db_session = DBConn.get_db_session()
        tl = db_session.query(Timeline). \
                filter(Timeline.name == name.strip()).first()
        return tl
    
    @staticmethod
    def update(name, since_id):
        if name == None:
            raise ValueError("'name' may not be None.")
        if since_id == None:
            raise ValueError("'since_id' may not be None.")
        tl = Timeline.get_by_name(name)
        if tl == None:
            tl = Timeline(name, since_id)
            return tl.since_id
        if tl.since_id < since_id:
            tl.since_id = since_id
            DBConn.get_db_session().commit()
        since_id = int(tl.since_id)
        return since_id

class DBConn(object):
    def __new__(type, *args, **kwargs):
        if not '_the_instance' in type.__dict__ or not type.__dict__.get('_the_instance'):
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
            self.sessions = {}
    
    def __del__(self):
        for pid in self.sessions:
            self.sessions[pid].close()
        self.engine.dispose()
    
    def get_session(self):
        pid = str(current_process().pid)
        session = self.sessions.get(pid)
        if session == None:
            Session = sqlalchemy.orm.sessionmaker(bind=self.engine)
            self.sessions[pid] = Session()
        return self.sessions[pid]
    
    def add(self, obj):
        if obj == None:
            raise ValueError("'obj' may not be None.")
        db_session = self.get_session()
        try:
            db_session.add(obj)
            db_session.commit()
        except IntegrityError, e:
            db_session.rollback()
            raise e
        except FlushError, e:
            db_session.rollback()
            raise e
        return True
    
    @staticmethod
    def get_db_session():
        db = DBConn()
        return db.get_session()
