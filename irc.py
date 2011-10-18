from multiprocessing import Process, Lock
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from db import User, Post
from apicalls import IdenticaError
from config import Config
import sys, time, traceback, config, re

command_hlp = {
    'help': {'usage': 'help [<command >]', 'text': 'Show help.'},
    'identify': {'usage': 'identify <username> <password>', 'text': 'Identify yourself.'},
    "history": {'usage': 'history [{YYYY-MM-DD | <username>}]', 'text': 'Show history of posts of the day with date YYYY-MM-DD, the posts of the user <username> (spline nickname), or the last posted post (no parameter).'},
    "post": {'usage': 'post <message>', 'text': 'Post a message to identi.ca'},
    "delete": {'usage': 'remove {<post_id> | last}', 'text': 'Remove last post or the post with the id <post_id>'},
    "reply": {'usage': 'reply {<post_id> | last} <message>', 'text': 'reply to last post or the post with the id <post_id>'}
}

class TwitterBot(SingleServerIRCBot):
    def __init__(self,posting_api,channel,nickname,server,port=6667, short_symbols='',since_id=0):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.posting_api = posting_api
        self.short_symbols = short_symbols
        self.since_id = since_id
        self.since_id_lock = Lock()
        self.mention_grabber = None

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        self.mention_grabber = Process(
                target=TwitterBot.get_mentions, 
                args=(
                        conn, 
                        self.channel, 
                        self.posting_api, 
                        self.since_id,
                        self.since_id_lock,
                    )
            )
        self.mention_grabber.start()
        conn.join(self.channel)
    
    def on_disconnect(self, conn, event):
        mention_grabber.terminate()

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
    
    def generate_help_text(self, args):
        if len(args) == 0:
            return 'Available commands: '+' '.join(command_hlp.keys())
        else:
            help = command_hlp[args[0]]
            return 'Usage: %s (%s)' % (help['usage'], help['text'])
    
    def _history_reply(self, conn, nick, posts):
        if len(posts) == 0:
            conn.privmsg(nick, "%s, no posts." % nick)
            return
        for post in posts:
            username = post.user.ldap_id
            try:
                status = self.posting_api.GetStatus(post.status_id)
            except IdenticaError, e:
                if str(e) == 'Status deleted':
                    Post.delete(post.status_id)
                    continue
                else:
                    raise e
            created_at = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(status.created_at_in_seconds)
            )
            reply = "%s: %s (%s, id = %d)\r\n" % \
                    (username, status.text, created_at, status.id)
            conn.privmsg(nick, reply)
    
    def get_history(self, conn, event, nick, args):
        if len(args) == 1:
            session, posts = Post.get_last()
            reply = self._history_reply(conn, nick, posts)
            session.close()
        elif len(args) > 1:
            if re.match('^[0-9]{4}-[0-1][0-9]-[0-9]{2}$',args[1]):
                session, posts = Post.get_by_day(args[1])
            else:
                session, posts = Post.get_by_user(args[1])
        reply = self._history_reply(conn, nick, posts)
        session.close()
    
    def do_post(self, conn, event, nick, message, in_reply_to_status_id = None):
        try:
            if len(message) > 0:
                status = self.posting_api.PostUpdate(event.source(), message, in_reply_to_status_id)
                reply = "%s, I posted this status with id %d" % (nick, status.id)
            else:
                reply = "%s, you want to post an empty string?" % nick
        except IdenticaError, e:
            if str(e).find("Text must be less than or equal to") == 0:
                reply = "%s, text must be less than or equal to " % nick + \
                        "140 characters. Your text has length %d." % len(message)
            else:
                reply = "%s, %s", (nick, e)
        except User.NotLoggedIn:
            reply = "You must be identified to use the 'post' command"
        if event.target() in self.channels.keys():
            conn.privmsg(event.target(), reply)
        else:
            conn.privmsg(nick, reply)
    
    def do_identify(self, conn, event, nick, username, password):
        user = User.get_by_user_id(username)
        if user == None:
            reply = "%s, username or password is wrong." % nick
        else:
            if user.login(event.source(), password):
                reply = "%s, operation successful!" % nick
            else:
                reply = "%s, username or password is wrong." % nick
        if event.target() in self.channels.keys():
            conn.privmsg(event.target(), reply)
        else:
            conn.privmsg(nick, reply)
    
    def do_delete(self, conn, event, nick, arg):
        if arg == 'last':
            session, posts = Post.get_last(1)
            session.close()
            if len(posts) > 0:
                status_id = posts[0].status_id
            else:
                reply = "%s, I don't know any posts." % nick
                if event.target() in self.channels.keys():
                    conn.privmsg(event.target(), reply)
                else:
                    conn.privmsg(nick, reply)
        elif re.match('^[0-9]+$', arg):
            status_id = int(arg)
        else:
            self.reply_usage('remove {<post_id> | last}')
            return
        try:
            self.posting_api.DestroyStatus(event.source(), status_id)
            reply = "%s, status %d deleted" % (nick,status_id)
        except IdenticaError, e:
            if str(e) == 'Status deleted':
                reply = "%s, status %d already deleted." % (nick,status_id)
            else:
                reply = "%s, %s" % (nick,e)
        except Post.DoesNotExist:
            reply = "%s, status %d not tracked." % (nick,status_id)
        except User.NotLoggedIn, e:
            reply = "%s, %s" (nick, e)
        if event.target() in self.channels.keys():
            conn.privmsg(event.target(), reply)
        else:
            conn.privmsg(nick, reply)
    
    def do_reply(self, conn, event, nick, recipient, message):
        self.since_id_lock.acquire()
        conf = Config() 
        if recipient == 'last':
            status_id = conf.identica.since_id
        elif recipient.find('@') == 0:
            pass            # to be done
        elif re.match('^[0-9]+$', recipient):
            status_id = int(recipient)
        else:
            self.reply_usage(conn, event, nick, 'reply {<post_id> | last} <message>')
            return
        self.since_id_lock.release()
        status = self.posting_api.GetStatus(status_id)
        if message.find('@'+status.user.screen_name) < 0:
            message = '@'+status.user.screen_name+' '+message
        self.do_post(conn, event, nick, message, status_id)
    
    def reply_usage(self, conn, event, nick, message):
        reply = "%s, Usage: %s" % (nick, message)
        if event.target() in self.channels.keys():
            conn.privmsg(event.target(), reply)
        else:
            conn.privmsg(nick, reply)
    
    def do_command(self, event, cmd):
        nick = nm_to_n(event.source())
        conn = self.connection
        tokens = cmd.split()
        command = tokens[0]
        if command == "help":
            reply = self.generate_help_text(tokens[1:])
            conn.privmsg(nick, reply)
            return
        elif command == "identify":
            if len(tokens) == 3:
                username = tokens[1]
                password = tokens[2]
                self.do_identify(conn, event, nick, username, password)
                return
        elif command == "history":
            self.get_history(conn, event, nick, tokens)
            return
        elif command == "post":
            message = cmd[len("post "):].strip()
            if len(message) > 0:
                self.do_post(conn, event, nick, message)
                return
        elif command == "delete":
            if len(tokens) == 2:
                self.do_delete(conn, event, nick, tokens[1])
                return
        elif command == "reply":
            if len(tokens) > 2:
                message = cmd[len("reply "+tokens[1])+1:].strip()
                self.do_reply(conn, event, nick, tokens[1].strip(), message)
                return
        else:
            reply = "Unknown command: " + cmd
            if event.target() in self.channels.keys():
                conn.privmsg(event.target(), reply)
            else:
                conn.privmsg(nick, reply)
            return
        self.reply_usage(conn, event, nick, command_hlp[command]['usage'])
    
    @staticmethod
    def get_mentions(conn, channel, posting_api, since_id, since_id_lock):
        timestr = lambda sec: time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(sec)
            )
        while 1:
            time.sleep(10)
            since_id_lock.acquire()
            statuses = posting_api.GetMentions(since_id)
            if len(statuses) > 0 and conn.socket != None:   # if there is a connection
                since_id = max(statuses, key = lambda s: s.id).id
                conf = Config()
                conf.identica.since_id = since_id
                since_id_lock.release()
                for status in statuses:
                    mention = "@%s: %s (%s, %s)" % \
                            (status.user.screen_name,
                             status.text, 
                             timestr(status.created_at_in_seconds),
                             "https://identi.ca/notice/%d" % status.id
                            )
                    conn.privmsg(channel, mention)
            else:
                since_id_lock.release()
    
    def start(self):
        try:
            SingleServerIRCBot.start(self)
        except BaseException:
            sys.stderr.write(traceback.format_exc())
            self.mention_grabber.terminate()
            exit(1)
        
