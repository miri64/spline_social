import sqlite3
from hashlib import sha256 as sha

class DBConn(object):
    def __new__(type, *args, **kwargs):
        if not '_the_instance' in type.__dict__:
            type._the_instance = object.__new__(type)
        return type._the_instance
    
    def __init__(self, name = None):
        if name != None:
            self.conn = sqlite3.connect(name)
            self.cursor = self.conn.cursor()
            self._create_db()
    
    def _create_db(self):
        self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user (
                    user_id TEXT PRIMARY KEY NOT NULL,
                    password TEXT NOT NULL,
                    banned BOOLEAN DEFAULT FALSE,
                    gets_mail BOOLEAN DEFAULT FALSE,
                    salt TEXT NOT NULL
                )"""
            )
        self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS login (
                    fk_user_id TEXT NOT NULL 
                        REFERENCES user (user_id) 
                            ON DELETE CASCADE
                            ON UPDATE CASCADE,
                    irc_nick TEXT PRIMARY KEY NOT NULL,
                    expires DATETIME NOT NULL,
                    UNIQUE (fk_user_id, irc_nick) ON CONFLICT REPLACE
                )"""
            )
        self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS post (
                    status_id PRIMARY_KEY NOT NULL,
                    fk_user_id TEXT NOT NULL
                        REFERENCES user (user_id) 
                            ON DELETE CASCADE
                            ON UPDATE CASCADE,
                    UNIQUE (status_id, fk_user_id) ON CONFLICT REPLACE
                )"""
            )
        self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth (
                    type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    secret TEXT NOT NULL,
                    UNIQUE (type, key, secret) ON CONFLICT IGNORE
                )"""
            )
        self.conn.commit()
    
    def execute(self, command, *args):
        self.cursor.execute(command, args)
        self.conn.commit()
    
    def executes(self, commands):
        for command, args in commands:
            self.cursor.execute(command, args)
        self.conn.commit()
    
    def select(self,table, columns = ['*'], where = None, limit = None):
        column_list = ''
        for column in columns:
            column_list += column + ','
        column_list = column_list.strip(',')
        if where != None:
            where_clause = ' WHERE '
            for n, column in enumerate(where,1):
                where_clause += '`%s` = "%s"' % (column, where[column])
                if n != len(where):
                    where_clause += ' AND '
        else:
            where_clause = ''
        if limit != None:
            limit_clause = ' LIMIT `%d`' % limit
        else:
            limit_clause = ''
        self.cursor.execute(
                'SELECT %s FROM %s%s%s' % \
                        (column_list,table,where_clause,limit_clause)
            )
        return [row for row in self.cursor]

class User:
    def __init__(self, user_id, password, banned = False, gets_mail = False, salt = None):
        self.__dict__['_vars'] = {}
        self.__dict__['db'] = DBConn()
        self.user_id = user_id
        if salt == None
            self.salt = ''.join(map(lambda x:chr(range(255)[ord(x)%255]), os.urandom(64)))
        else:
            self.salt = salt
        self.password = (password,)
        self.banned = banned
        self.gets_mail = gets_mail
    
    def __getattr__(self, attr):
        try:
            return self._vars[attr]
        except KeyError,e:
            raise AttributeError("User has no Attribute %s" % e)
    
    def __setattr__(self, attr, value):
        if attr != 'password':
            if attr == 'banned' or attr == 'gets_mail':
                if value == 0 or value == None or value == False:
                    self._vars[attr] = False
                else:
                    self._vars[attr] = True
            else:
                self._vars[attr] = value
        else:
            if isinstance(value, str):
                self._vars[attr] = self._get_pwhash(value)
            else
                self._vars[attr] = value[0]
    
    def _get_pwhash(self, password):
        hash = sha()
        hash.update(password)
        hash.update(self.salt)
        return hash.hexdigest()
    
    @staticmethod
    def get_all():
        db = DBConn()
        results = db.select('user')
        return [User(*result) for result in results]
    
    @staticmethod
    def get(user_id):
        db = DBConn()
        results = db.select('user',where={'user_id': user_id})
        if len(results) > 0:
            result = results[0]
            return User(*result)
        else:
            return None
    
    def validate_password(self,password):
        return self.password == self._get_pwhash(password)
    
    def in_db(self):
        return User.get(self.user_id) != None

    def save(self):
        if self.in_db():
            self.db.execute(
                    """ UPDATE user
                        SET password = ?,
                            banned = ?,
                            gets_mail = ?,
                            salt = ?
                        WHERE user_id = ?""",
                    self.password,
                    self.banned,
                    self.gets_mail,
                    self.salt,
                    self.user_id
                )
        else:
            self.db.execute(
                    """ INSERT INTO user
                        VALUES (?,?,?,?,?)""",
                    self.user_id,
                    self.password,
                    self.banned,
                    self.gets_mail,
                    self.salt
                )

