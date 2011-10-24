#!/usr/bin/env python
import tests
import os, unittest, random, time, datetime
import apicalls, db, irc
from itertools import chain
from irclib import nm_to_n

TEST_SUBJECTS = 10

def random_str(max_len = 30):
    return unicode(''.join( 
            map(
                    lambda x:
                            './&%$!"12345678890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'[ord(x)%65], 
                    os.urandom(random.choice(range(1,max_len)))
            )
        ))

def random_irc_id():
    return random_str(10)+'!'+random_str(8)+'@'+random_str(10)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = db.DBConn(driver='sqlite',name='./tests.sqlite')
    
    def tearDown(self):
        db.DBConn._the_instance = None
        os.remove('./tests.sqlite')

class TestDatabaseUserIntegrity(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.user_ids = [random_str() for _ in range(TEST_SUBJECTS)]
        self.passwords = [random_str() for _ in range(TEST_SUBJECTS)]
        self.example_id = random.choice(range(TEST_SUBJECTS))
    
    def test_create_user_none_user_id(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.User(None, self.passwords[i])
    
    def test_create_user_none_password(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.User(self.user_ids[i], None)
        with self.assertRaises(ValueError):
            db.User(self.user_ids[i], '')
    
    def test_create_user_duplicate_user_id(self):
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            password = random_str()
            if password != self.passwords[i]:
                break
        db.User(self.user_ids[i], self.passwords[i])
        with self.assertRaises(db.FlushError):
            db.User(self.user_ids[i], password)

class TestDatabaseUserMethods(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.user_ids = [random_str() for _ in range(TEST_SUBJECTS)]
        self.passwords = [random_str() for _ in range(TEST_SUBJECTS)]
        self.users = [db.User(*values) 
                for values in zip(
                        self.user_ids, 
                        self.passwords
                    )
            ]
    
    def test_setattr(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.users[i].user_id = None
        
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.users[i].salt = None
    
    def test_setattr_password(self):
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            password = random_str()
            if password != self.passwords[i]:
                break
        self.users[i].password = password
        self.assertTrue(self.users[i].validate_password(password))
    
    def test_validate_password_none(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.User.EmptyPasswordException):
            self.users[i].validate_password(None)
    
    def test_validate_password_wrong(self):
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            password = random_str()
            if password != self.passwords[i]:
                break
        self.assertFalse(self.users[i].validate_password(password))
    
    def test_login(self):
        i = random.choice(range(TEST_SUBJECTS))
        irc_id = random_irc_id()
        self.assertTrue(self.users[i].login(irc_id, self.passwords[i]))
        login = db.Login.get(irc_id)
        self.assertTrue(login != None)
    
    def test_update_login(self):
        i = random.choice(range(TEST_SUBJECTS))
        irc_id = random_irc_id()
        self.assertTrue(self.users[i].login(irc_id, self.passwords[i]))
        last = db.Login.get(irc_id).expires
        time.sleep(0.1)
        self.users[i].update_login(irc_id)
        self.assertTrue(db.Login.get(irc_id).expires != last)
    
    def test_add_post_none_status(self):
        i = random.choice(range(TEST_SUBJECTS))
        irc_id = random_irc_id()
        with self.assertRaises(ValueError):
            self.users[i].add_post(None)
    
    def test_get_by_user_id(self):
        with self.assertRaises(ValueError):
            db.User.get_by_user_id(None)
        i = random.choice(range(TEST_SUBJECTS))
        user = db.User.get_by_user_id(self.user_ids[i])
        self.assertTrue(user.validate_password(self.passwords[i]))
    
    def test_get_by_irc_id(self):
        with self.assertRaises(ValueError):
            db.User.get_by_irc_id(None)
        irc_id = random_irc_id()
        with self.assertRaises(db.User.NotLoggedIn):
            db.User.get_by_irc_id(irc_id)
        i = random.choice(range(TEST_SUBJECTS))
        self.users[i].login(irc_id, self.passwords[i])
        user = db.User.get_by_irc_id(irc_id)
        self.assertTrue(user.user_id == self.user_ids[i])
    
    def test_delete(self):
        with self.assertRaises(ValueError):
            db.User.delete(None)
        i = random.choice(range(TEST_SUBJECTS))
        db.User.delete(self.users[i])
        user = db.User.get_by_user_id(self.user_ids[i])
        self.assertTrue(user == None)

class TestDatabasePostIntegrity(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
    
    def test_status_id_none(self):
        status = tests.testclasses.Status()
        status.id = None
        user = db.User(random_str(),random_str())
        with self.assertRaises(ValueError):
            user.add_post(status)
    
    def test_created_at_none(self):
        status = tests.testclasses.Status()
        status.created_at_in_seconds = None
        user = db.User(random_str(),random_str())
        with self.assertRaises(ValueError):
            user.add_post(status)
    
    def test_duplicate_status_id(self):
        user = db.User(random_str(),random_str())
        status1 = tests.testclasses.Status()
        status2 = tests.testclasses.Status()
        status2.id = status1.id
        user.add_post(status1)
        with self.assertRaises(db.FlushError):
            user.add_post(status2)

class TestDatabasePostMethods(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.user_ids = [random_str() for _ in range(max([TEST_SUBJECTS/4,1]))]
        self.passwords = [random_str() for _ in range(max([TEST_SUBJECTS/4,1]))]
        self.users = [db.User(*values) 
                for values in zip(
                        self.user_ids, 
                        self.passwords
                    )
            ]
        self.statuses = [tests.testclasses.Status() for _ in range(TEST_SUBJECTS)]
        self.post_users = [random.choice(self.users) for _ in range(TEST_SUBJECTS)]
        self.posts = [user.add_post(status) for user, status in zip(self.post_users,self.statuses)]
    
    def test_setattr(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.posts[i].status_id = None
            
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.posts[i].created_at = None
            
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.posts[i].poster_id = None
        
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            created_at = datetime.datetime.fromtimestamp(
                    float(random.randint(0, (2**32)-1))
                )
            if created_at != self.posts[i].created_at:
                break
        self.posts[i].created_at = created_at
        post = db.Post.get(self.statuses[i].id)
        self.assertTrue(post.created_at == created_at)
    
    def test_gets(self):
        i = random.choice(range(TEST_SUBJECTS))
        post = db.Post.get(self.statuses[i].id)
        self.assertFalse(post == None)
        with self.assertRaises(ValueError):
            db.Post.get(None)
        
        i = random.choice(range(TEST_SUBJECTS))
        user_id = self.post_users[i].user_id
        posts = db.Post.get_by_user_id(user_id)
        self.assertTrue(len(posts) > 0)
        self.assertTrue(
                reduce(
                        lambda x,y: x and y,
                        [user_id == post.user.user_id for post in posts],
                        True
                    )
            )
        with self.assertRaises(ValueError):
            db.Post.get_by_user_id(None)
        
        i = random.choice(range(TEST_SUBJECTS))
        user_id = self.post_users[i].user_id
        irc_id = random_irc_id()
        self.post_users[i].login(irc_id, self.passwords[self.user_ids.index(user_id)])
        posts = db.Post.get_by_irc_id(irc_id)
        self.assertTrue(len(posts) > 0)
        self.assertTrue(
                reduce(
                        lambda x,y: x and y,
                        [user_id == post.user.user_id for post in posts],
                        True
                    )
            )
        with self.assertRaises(ValueError):
            db.Post.get_by_user_id(None)
        
        i = random.choice(range(TEST_SUBJECTS))
        post = db.Post.get_by_day(
                datetime.datetime.fromtimestamp(
                    self.statuses[i].created_at_in_seconds
                ).strftime("%Y-%m-%d")
            )
        self.assertFalse(post == None)
        with self.assertRaises(ValueError):
            db.Post.get_by_day(None)
    
    def test_mark_deleted(self):
        exception = apicalls.IdenticaError('Status deleted.')
        with self.assertRaises(ValueError):
            db.Post.mark_deleted(None,exception)
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.Post.mark_deleted(self.statuses[i].id,None)
        i = random.choice(range(TEST_SUBJECTS))
        db.Post.mark_deleted(self.statuses[i].id,exception)
        post = self.posts[i]
        self.assertTrue(post.deleted)
        self.assertTrue(post.deleter_id == 'By API')
        while 1:
            status_id = random.randint(0, (2**32)-1)
            if status_id not in [status.id for status in self.statuses]:
                break
        with self.assertRaises(db.Post.DoesNotExist):
            db.Post.mark_deleted(status_id,exception)
    
    def test_delete(self):
        irc_id = random_irc_id()
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.Post.delete(None, irc_id)
        
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.Post.delete(self.statuses[i].id, None)
        
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.User.NotLoggedIn):
            db.Post.delete(self.statuses[i].id, irc_id)
        
        i = random.choice(range(TEST_SUBJECTS))
        j = random.choice(range(max([TEST_SUBJECTS/4,1])))
        self.users[j].login(irc_id, self.passwords[j])
        db.Post.delete(self.statuses[i].id, irc_id)
        post = db.Post.get(self.statuses[i].id)
        self.assertTrue(post.deleter.user_id == self.users[j].user_id)
        
        while 1:
            status_id = random.randint(0, (2**32)-1)
            if status_id not in [status.id for status in self.statuses]:
                break
        with self.assertRaises(db.Post.DoesNotExist):
            db.Post.delete(status_id,irc_id)

class TestDatabaseLoginIntegrity(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
    
    def test_irc_id_none(self):
        password = random_str()
        user = db.User(random_str(),password)
        with self.assertRaises(ValueError):
            user.login(None, password)
    
class TestDatabaseLoginMethods(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.user_ids = [random_str() for _ in range(max([TEST_SUBJECTS/4,1]))]
        self.passwords = [random_str() for _ in range(max([TEST_SUBJECTS/4,1]))]
        self.users = [db.User(*values) 
                for values in zip(
                        self.user_ids, 
                        self.passwords
                    )
            ]
        self.irc_ids = [random_irc_id() for _ in range(TEST_SUBJECTS)]
        login_users_num = [random.choice(range(max([TEST_SUBJECTS/4,1]))) for _ in range(TEST_SUBJECTS)]
        self.login_users = [self.users[i] for i in login_users_num]
        self.login_passwords = [self.passwords[i] for i in login_users_num]
        for user,irc_id,password in \
                zip(self.login_users,self.irc_ids,self.login_passwords):
            user.login(irc_id,password)
        self.logins = map(db.Login.get, self.irc_ids)
    
    def test_setattr(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.logins[i].irc_id = None
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            expires = datetime.datetime.fromtimestamp(
                    float(random.randint(0, (2**32)-1))
                )
            if expires != self.logins[i].expires:
                break
        with self.assertRaises(AttributeError):
            self.logins[i].expires = expires
    
    def test_get(self):
        with self.assertRaises(ValueError):
            db.Login.get(None)
        while 1:
            irc_id = random_irc_id()
            if irc_id not in self.irc_ids:
                break
        login = db.Login.get(irc_id)
        self.assertTrue(login == None)
        
        i = random.choice(range(TEST_SUBJECTS))
        login = db.Login.get(self.irc_ids[i])
        self.assertTrue(login.user.user_id == self.login_users[i].user_id)
    
    def test_update(self):
        i = random.choice(range(TEST_SUBJECTS))
        old_expires = self.logins[i].expires
        time.sleep(0.1)
        self.logins[i].update()
        self.assertFalse(old_expires == self.logins[i].expires)

class TestDatabaseTimelineIntegrity(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
    
    def test_name_none(self):
        since_id = random.randint(0, (2**32)-1)
        with self.assertRaises(ValueError):
            db.Timeline(None,since_id)
    
    def test_since_id_none(self):
        name = random_str()
        with self.assertRaises(ValueError):
            db.Timeline(name,None)
    
    def test_duplicate_name(self):
        name = random_str()
        since_id = random.randint(0, (2**32)-1)
        db.Timeline(name,since_id)
        since_id = random.randint(0, (2**32)-1)
        with self.assertRaises(db.IntegrityError):
            db.Timeline(name,since_id)

class TestDatabaseTimelineMethods(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.names = [random_str() for _ in range(TEST_SUBJECTS)]
        self.since_ids = [random.randint(0, (2**32)-1) for _ in range(TEST_SUBJECTS)]
        self.timelines = [db.Timeline(*values) for values in zip(self.names,self.since_ids)]
    
    def test_setattr(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.timelines[i].name = None
        
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(db.IntegrityError):
            self.timelines[i].since_id = None
        
        i = random.choice(range(TEST_SUBJECTS))
        while 1:
            since_id = random.randint(0, (2**32)-1)
            if since_id not in self.since_ids:
                break
        self.timelines[i].since_id = since_id
    
    def test_get_by_name(self):
        with self.assertRaises(ValueError):
            db.Timeline.get_by_name(None)
        i = random.choice(range(TEST_SUBJECTS))
        tl = db.Timeline.get_by_name(self.names[i])
        self.assertTrue(tl.since_id == self.since_ids[i])
    
    def test_update(self):
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.Timeline.update(self.names[i],None)
        
        since_id = random.randint(0, (2**32)-1)
        i = random.choice(range(TEST_SUBJECTS))
        with self.assertRaises(ValueError):
            db.Timeline.update(None, since_id)
        
        i = random.choice(range(TEST_SUBJECTS))
        since_id = random.randint(self.since_ids[i]+1, (2**32)-1)
        db.Timeline.update(self.names[i], since_id)
        tl = db.Timeline.get_by_name(self.names[i])
        self.assertTrue(tl.since_id == since_id)

def test_db():
    test_cases = [
            TestDatabaseUserIntegrity,
            TestDatabaseUserMethods,
            TestDatabasePostIntegrity,
            TestDatabasePostMethods,
            TestDatabaseLoginIntegrity,
            TestDatabaseLoginMethods,
            TestDatabaseTimelineIntegrity,
            TestDatabaseTimelineMethods
        ]
    suite = unittest.TestSuite(chain(*[
            map(test_case, unittest.TestLoader().getTestCaseNames(test_case))
            for test_case in test_cases
        ]))
    print 'Testing db.py: '
    unittest.TextTestRunner().run(suite)

class TestIRCCommandHandler(TestDatabase):
    def setUp(self):
        TestDatabase.setUp(self)
        self.api = tests.testclasses.DummyApi(TEST_SUBJECTS)
        self.channel = '#'+random_str(5)
        self.nickname = random_str()
        self.bot = irc.TwitterBot(self.api, self.channel, '', nickname=self.nickname)
        self.connection = tests.testclasses.Connection(self.nickname)
        self.bot.connection = self.connection
        self.bot.channels = {self.channel: ''}
        
        self.source = random_irc_id()
        self.target = self.nickname
        self.event = tests.testclasses.Event(self.source,self.target)
        
        self.command = irc.CommandHandler(self.bot, self.connection, self.event)
    
    def tearDown(self):
        TestDatabase.tearDown(self)
        self.bot = None
        self.api = None
        self.connection = None
        self.event = None
        self.command = None
    
    def generate_usage_reply(self,command):
        if self.target == self.channel:
            reply = "%s: usage: %s" % \
                (   irc.nm_to_n(self.source),
                    irc.CommandHandler.command_help[command]['usage']
                )
        else:
            reply = "Usage: %s" % \
                    irc.CommandHandler.command_help[command]['usage']
        return reply
    
    def test_do_command_help_without_param(self):
        self.command.do('help')
        self.assertTrue('Available commands: '+
                ', '.join(irc.CommandHandler.command_help.keys())
            in self.connection.get_all_msgs())
    
    def test_do_command_help_with_param(self):
        command = random.choice(irc.CommandHandler.command_help.keys())
        self.command.do('help '+command)
        help = irc.CommandHandler.command_help[command]
        reply = '%s (%s)' % (help['usage'], help['text'])
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_admin_without_param(self):
        command = 'admin'
        self.command.do(command)
        reply = self.generate_usage_reply(command)
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_admin_with_param_legal(self):
        command = 'admin'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = True
        user2.admin = False
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(user2.admin)
        reply = 'You made %s an admin.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.admin)
        reply = 'You took admin rights from %s.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        user2_irc_id = random_irc_id()
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2.admin = False
        user2.login(user2_irc_id,password2)
        self.command.do('%s %s' % (command, user2_irc_id))
        self.assertTrue(user2.admin)
        reply = 'You made %s an admin.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_admin_with_param_illegal(self):
        command = 'admin'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = False
        
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.admin)
        reply = "IRC-User '%s' not logged in." % nm_to_n(self.source)
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.admin)
        reply = 'You are no admin.'
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_admin_self(self):
        command = 'admin'
        password = random_str()
        user = db.User(random_str(), password)
        user.admin = True
        
        user.login(self.source,password)
        self.command.do('%s %s' % (command, self.source))
        self.assertTrue(user.admin)
        reply = 'You can not strip yourself of your admin rights.'
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_ban_without_param(self):
        command = 'ban'
        self.command.do(command)
        reply = self.generate_usage_reply(command)
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_ban_with_param_legal(self):
        command = 'ban'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = True
        user2.banned = False
        
        user2_irc_id = random_irc_id()
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(user2.banned)
        reply = 'You banned user %s.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2_irc_id = random_irc_id()
        user2.banned = False
        user2.login(user2_irc_id,password2)
        self.command.do('%s %s' % (command, user2_irc_id))
        self.assertTrue(user2.banned)
        reply = 'You banned user %s.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_ban_with_param_illegal(self):
        command = 'ban'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = False
        user2.banned = False
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.banned)
        reply = "IRC-User '%s' not logged in." % nm_to_n(self.source)
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2.banned = True
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2.banned = False
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.banned)
        reply = 'You are no admin.'
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        user1.banned = True
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.banned)
        reply = 'You are banned.'
        self.assertTrue(self.connection.got_message(reply))
        
    def test_do_command_ban_self(self):
        command = 'ban'
        password = random_str()
        user = db.User(random_str(), password)
        user.admin = True
        user.banned = False
        
        user.login(self.source,password)
        self.command.do('%s %s' % (command, self.source))
        self.assertTrue(not user.banned)
        reply = 'You can\'t ban yourself.'
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_unban_without_param(self):
        command = 'unban'
        self.command.do(command)
        reply = self.generate_usage_reply(command)
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_unban_with_param_legal(self):
        command = 'unban'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = True
        user2.banned = True
        
        user2_irc_id = random_irc_id()
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(not user2.banned)
        reply = 'You unbanned user %s.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2_irc_id = random_irc_id()
        user2.banned = True
        user2.login(user2_irc_id,password2)
        self.command.do('%s %s' % (command, user2_irc_id))
        self.assertTrue(not user2.banned)
        reply = 'You unbanned user %s.' % user2.user_id
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_unban_with_param_illegal(self):
        command = 'unban'
        password1 = random_str()
        password2 = random_str()
        user1 = db.User(random_str(), password1)
        user2 = db.User(random_str(), password2)
        user1.admin = False
        user2.banned = True
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(user2.banned)
        reply = "IRC-User '%s' not logged in." % nm_to_n(self.source)
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2.banned = True
        user1.login(self.source,password1)
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(user2.banned)
        reply = 'You are no admin.'
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        password2 = random_str()
        user2 = db.User(random_str(), password2)
        user2.banned = True
        user1.banned = True
        self.command.do('%s @%s' % (command, user2.user_id))
        self.assertTrue(user2.banned)
        reply = 'You are banned.'
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_identify_without_param(self):
        command = 'identify'
        self.command.do(command)
        reply = self.generate_usage_reply(command)
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_identify_with_param_legal(self):
        command = 'identify'
        password = random_str()
        user = db.User(random_str(), password)
        self.command.do('%s %s %s' % (command, user.user_id, password))
        self.assertTrue(db.Login.get(self.source) != None)
        reply = "You are now identified as %s." % user.user_id
        self.assertTrue(self.connection.got_message(reply))
        
    def test_do_command_identify_with_param_illegal(self):
        command = 'identify'
        password = random_str()
        user = db.User(random_str(), password)
        while 1:
            wrong_user_id = random_str()
            if wrong_user_id != user.user_id:
                break
        self.command.do('%s %s %s' % (command, wrong_user_id, random_str()))
        self.assertTrue(db.Login.get(self.source) == None)
        reply = "Username or password is wrong."
        self.assertTrue(self.connection.got_message(reply))
        self.connection.empty_msgs()
        
        while 1:
            wrong_password = random_str()
            if wrong_password != password:
                break
        self.command.do('%s %s %s' % (command, user.user_id, wrong_password))
        self.assertTrue(db.Login.get(self.source) == None)
        reply = "Username or password is wrong."
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_history_without_param(self):
        command = 'history'
        self.connection.empty_msgs()
        self.command.do(command)
        self.assertTrue(len(self.connection.get_all_msgs()) > 0)
        
        status = random.choice(self.api.posts)
        user = db.User(random_str(), random_str())
        user.add_post(status)
        self.command.do(command)
        reply = "%s: %s (%s, id = %d)" % (user.user_id, status.text, status.created_at, status.id)
        self.assertTrue(len(self.connection.get_all_msgs()) > 0)
        
    def test_do_command_history_with_param_user_id(self):
        command = 'history'
        self.connection.empty_msgs()
        self.command.do('%s @%s' % (command, random_str()))
        self.assertTrue(len(self.connection.get_all_msgs()) > 0)
        
        status = random.choice(self.api.posts)
        user = db.User(random_str(), random_str())
        user.add_post(status)
        self.command.do('%s @%s' % (command, user.user_id))
        reply = "%s: %s (%s, id = %d)" % (user.user_id, status.text, status.created_at, status.id)
        self.assertTrue(self.connection.got_message(reply))
        
    def test_do_command_history_with_param_irc_id(self):
        command = 'history'
        self.connection.empty_msgs()
        self.command.do('%s %s' % (command, random_str()))
        self.assertTrue(len(self.connection.get_all_msgs()) > 0)
        
        status = random.choice(self.api.posts)
        password = random_str()
        user = db.User(random_str(), password)
        user.add_post(status)
        user.login(self.source, password)
        self.command.do('%s %s' % (command, self.source))
        reply = "%s: %s (%s, id = %d)" % (user.user_id, status.text, status.created_at, status.id)
        self.assertTrue(self.connection.got_message(reply))
    
    def test_do_command_history_with_param_day(self):
        command = 'history'
        self.connection.empty_msgs()
        self.command.do('%s %s' % (command, random_str()))
        self.assertTrue(len(self.connection.get_all_msgs()) > 0)
        
        status = random.choice(self.api.posts)
        user = db.User(random_str(), random_str())
        user.add_post(status)
        self.command.do('%s %s' % (command, datetime.datetime.fromtimestamp(status.created_at_in_seconds).strftime("%Y-%m-%d")))
        reply = "%s: %s (%s, id = %d)" % (user.user_id, status.text, status.created_at, status.id)
        self.assertTrue(self.connection.got_message(reply))

def test_irc():
    test_cases = [
            TestIRCCommandHandler,
        ]
    suite = unittest.TestSuite(chain(*[
            map(test_case, unittest.TestLoader().getTestCaseNames(test_case))
            for test_case in test_cases
        ]))
    print 'Testing irc.py: '
    unittest.TextTestRunner().run(suite)

def main():
    test_db()
    test_irc()

if __name__ == '__main__':
    import sys
    reload(sys)
    sys.setdefaultencoding('utf8')
    main()
