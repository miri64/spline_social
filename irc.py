from multiprocessing import Process
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from db import User, Post, Timeline
from apicalls import IdenticaError
import sys, time, traceback, re
from urllib2 import URLError
from datetime import datetime

class CommandHandler:
    class UsageError(Exception):
        def __init__(self, command):
            self.command = command
        
        def __repr__(self):
            return self.command
    
    command_help = {
            'bann': {
                    'usage': 'bann <username>',
                    'text': 'Banns a user and disables his or hers ability to post, delete posts and bann/unbann users.'
                },
            'help': {
                    'usage': 'help [<command >]', 
                    'text': 'Show help.'
                },
            'identify': {
                    'usage': 'identify <username> <password>', 
                    'text': 'Identify yourself.'
                },
            'history': {
                    'usage': 'history [{YYYY-MM-DD | <username>}]', 
                    'text': 'Show history of posts of the day with date YYYY-MM-DD, the posts of the user <username> (spline nickname), or the last 10 posted posts (no parameter).'
                },
            'post': {
                    'usage': 'post <message>', 
                    'text': 'Post a message to identi.ca.'
                },
            'delete': {
                    'usage': 'delete {<post_id> | last}', 
                    'text': 'Remove last post or the post with the id <post_id>.'
                },
            'reply': {
                    'usage': 'reply {<post_id> | last} <message>', 
                    'text': 'reply to last post or the post with the id <post_id>.'
                },
            'unbann': {
                    'usage': 'unbann <username>',
                    'text': 'Unbanns a user and reverts all effects of a bann.'
                },
        }
    
    def __init__(self, bot, conn, event):
        self.bot = bot
        self.conn = conn
        self.event = event
        
    def _get_nick(self):
        return nm_to_n(self.event.source())
    
    def _do_reply(self, reply):
        reply = reply.strip()
        channel = self.event.target()
        if channel in self.bot.channels.keys():
            reply = reply[0].lower() + reply[1:]
            reply = "%s: %s" % (self._get_nick(), reply)
            self.conn.privmsg(channel, reply)
        else:
            self._do_private_reply(reply)
    
    def _do_private_reply(self, reply):
        self.conn.privmsg(self._get_nick(), reply)
    
    def _do_usage_reply(self, command):
        reply = "Usage: %s" % CommandHandler.command_help[command]['usage']
        self._do_reply(reply)
    
    def do(self, command_str):
        command_f = {
                'help': self.do_help,
                'identify': self.do_identify,
                'history': self.do_history,
                'post': self.do_post,
                'delete': self.do_delete,
                'reply': self.do_reply,
            }
        args = command_str.split()
        command = args[0].strip()
        try:
            while 1:
                try:
                    if command == 'post':
                        message = command_str[len('post '):].strip()
                        command_f[command](message)
                    elif command == 'reply':
                        if len(args) < 2:
                            raise CommandHandler.UsageError(command)
                        recipient = args[1].strip()
                        message = command_str[len('reply '+recipient)+1:].strip()
                        command_f[command](recipient, message)
                    else:
                        try:
                            command_f[command](*args[1:])
                        except TypeError:
                            raise CommandHandler.UsageError(command)
                    return
                except URLError:
                    print "UrlError", e
                    time.sleep(0.2)
        except KeyError:
            reply = "Unknown command: " + cmd
        except CommandHandler.UsageError, e:
            reply = "Usage: %s" % CommandHandler.command_help[e.command]['usage']
        self._do_reply(reply)
    
    def _set_bann(self, username, bann_status):
        try:
            bannee = User.get_by_ldap_id(username)
            banner = User.get_by_irc_id(self.event.source())
            if banner.banned:
                reply = 'You are banned.'
                bannee.session.close()
                banner.session.close()
            elif bannee != None:
                bannee.banned = True
                reply = 'You %sbanned user %s.' % ('' if bann_status else 'un', username)
                bannee.session.commit()
                bannee.session.close()
                banner.session.close()
            else:
                reply = 'User %s does not exist.' % username
                banner.session.close()
        except User.NotLoggedIn, e:
            reply = str(e)
        self._do_reply(reply)
    
    def do_bann(self, username):
        self._set_bann(username, True)
    
    def do_help(self, command = None):
        if command == None:
            reply = 'Available commands: '+', '.join(CommandHandler.command_help.keys())
        else:
            help = CommandHandler.command_help[command]
            reply = '%s (%s)' % (help['usage'], help['text'])
        self._do_reply(reply)
    
    def do_identify(self, username, password):
        nick = self._get_nick()
        
        user = User.get_by_user_id(username)
        
        login_error_reply = "Username or password is wrong."
        if user == None:
            reply = login_error_reply
        else:
            if user.login(self.event.source(), password):
                reply = "Operation successful!"
            else:
                reply = login_error_reply
        self._do_reply(reply)
    
    def _generate_history_replies(self, posts):
        shown_posts = 0
        for post in posts:
            username = post.user.ldap_id
            try:
                status = self.bot.posting_api.GetStatus(post.status_id)
                created_at = post.created_at
                reply = "%s: %s (%s, id = %d)\r\n" % \
                        (username, status.text, created_at, status.id)
                self._do_private_reply(reply)
                shown_posts += 1
            except IdenticaError, e:
                if str(e).find('Status deleted') >= 0:
                    Post.mark_deleted(post.status_id, e)
                    continue
                else:
                    raise e
        if shown_posts == 0:
            self._do_private_reply("No posts.")
    
    def do_history(self, argument = None):
        if argument == None:
            session, posts = Post.get_last()
        else:
            if re.match('^[0-9]{4}-[0-1][0-9]-[0-9]{2}$',argument):
                session, posts = Post.get_by_day(argument)
            else:
                session, posts = Post.get_by_user(argument)
        self._generate_history_replies(posts)
        session.close()
    
    def do_post(self, message, in_reply_to_status_id = None):
        try:
            if len(message) > 0:
                status = self.bot.posting_api.PostUpdate(
                        self.event.source(), 
                        message, 
                        in_reply_to_status_id
                    )
                reply = "Posted this status with id %d" % status.id
            else:
                reply = "You want to post an empty string? I don't think so."
        except IdenticaError, e:
            if str(e).find("Text must be less than or equal to") >= 0:
                reply = "Text must be less than or equal to " + \
                        "140 characters. Your text has length %d." % len(message)
            else:
                reply = "%s" % e
        except User.NotLoggedIn, e:
            reply = str(e)
        except User.Banned, e:
            reply = str(e)
        self._do_reply(reply)
    
    def do_delete(self, argument):
        if argument == 'last':
            session, posts = Post.get_last(1)
            session.close()
            if len(posts) > 0:
                status_id = posts[0].status_id
            else:
                reply = "%s, I don't know any posts." % self._get_nick()
                if event.target() in self.channels.keys():
                    conn.privmsg(event.target(), reply)
                else:
                    conn.privmsg(nick, reply)
        elif re.match('^[0-9]+$', argument):
            status_id = int(argument)
        else:
            raise CommandHandler.UsageError('remove')
        try:
            self.bot.posting_api.DestroyStatus(
                    self.event.source(), 
                    status_id
                )
            reply = "Status %d deleted" % status_id
        except IdenticaError, e:
            if str(e).find('Status deleted') >= 0:
                reply = "Status %d already deleted." % status_id
                Post.mark_deleted(status_id)
            else:
                reply = str(e)
        except Post.DoesNotExist, e:
            reply = str(e)
        except User.NotLoggedIn, e:
            reply = str(e)
        except User.Banned, e:
            reply = str(e)
        self._do_reply(reply)
    
    def do_reply(self, recipient, message):
        if recipient == 'last':
            status_id = Timeline.get_by_name('mentions').since_id
        elif recipient.find('@') == 0:
            reply = "Direct user answer is not implemented yet."
            self._do_reply(reply)
            return
        elif re.match('^[0-9]+$', recipient):
            status_id = int(recipient)
        else:
            raise CommandHandler.UsageError('reply')
        status = self.bot.posting_api.GetStatus(status_id)
        self.do_post(message, status_id)
    
    def do_unbann(self, username):
        self._set_bann(username, False)

class TwitterBot(SingleServerIRCBot):
    def __init__(
            self,
            posting_api,
            channel,
            server,
            port=6667,
            nickname='spline_social',
            short_symbols='',
            mention_interval=120,
            since_id=0
        ):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.posting_api = posting_api
        self.short_symbols = short_symbols
        self.mention_interval = mention_interval
        self.since_id = Timeline.update('mentions', since_id)
        self.mention_grabber = None

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        self.mention_grabber = Process(
                target=TwitterBot.get_mentions, 
                args=(
                        conn, 
                        self.channel, 
                        self.mention_interval,
                        self.posting_api, 
                        self.since_id,
                    )
            )
        self.mention_grabber.start()
        conn.join(self.channel)
        print "Joined channel %s" % self.channel
    
    def on_disconnect(self, conn, event):
        if self.mention_grabber != None:
            self.mention_grabber.terminate()

    def on_privmsg(self, conn, event):
        self.do_command(event, event.arguments()[0])

    def on_pubmsg(self, conn, event):
        if event.arguments()[0][0] in self.short_symbols and \
                len(event.arguments()[0]) > 1:
            cmd = event.arguments()[0][1:]
            self.do_command(event, cmd)
        else:
            args = event.arguments()[0].split(":", 1)
            if len(args) == 1:
                args = event.arguments()[0].split(",", 1)
            if len(args) > 1 and \
                    irc_lower(args[0]) == irc_lower(self.connection.get_nickname()):
                cmd = args[1].strip()
            else:
                return
            self.do_command(event, cmd)
    
    def do_command(self, event, cmd):
        Process(
                target=CommandHandler(self,self.connection,event).do, 
                args=(cmd,)
            ).start()
   
    @staticmethod
    def get_mentions(conn, channel, interval, posting_api, since_id):
        timestr = lambda sec: time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(sec)
            )
        while 1:
            try:
                statuses = posting_api.GetMentions(since_id)
                if len(statuses) > 0 and conn.socket != None:   # if there is a connection
                    since_id = max(statuses, key = lambda s: s.id).id
                    Timeline.update('mentions', since_id)
                    for status in statuses:
                        mention = "@%s: %s (%s, %s)" % \
                                (status.user.screen_name,
                                 status.text, 
                                 timestr(status.created_at_in_seconds),
                                 "https://identi.ca/notice/%d" % status.id
                                )
                        conn.privmsg(channel, mention)
                time.sleep(interval)
            except BaseException, e:
                print 'Critical:', e
    
    def start(self):
        try:
            SingleServerIRCBot.start(self)
        except BaseException:
            sys.stderr.write(traceback.format_exc())
            if self.mention_grabber:
                self.mention_grabber.terminate()
            exit(1)
        
