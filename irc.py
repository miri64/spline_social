from multiprocessing import Process
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from db import User
from apicalls import IdenticaError
import sys, time, traceback, config

class TwitterBot(SingleServerIRCBot):
    def __init__(self,posting_api,channel,nickname,server,port=6667, short_symbols='',since_id=0):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.posting_api = posting_api
        self.short_symbols = short_symbols
        self.since_id = since_id
        self.mention_grabber = None

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        self.mention_grabber = Process(
                target=TwitterBot.get_mentions, 
                args=(conn, self.channel, self.posting_api, self.since_id)
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
        else:
            args = event.arguments()[0].split(":", 1)
            if len(args) == 1:
                args = event.arguments()[0].split(",", 1)
            if len(args) > 1 and \
                    irc_lower(args[0]) == irc_lower(self.connection.get_nickname()):
                cmd = args[1].strip()
        self.do_command(event, cmd)
    
    def do_post(self, conn, event, nick, message):
        try:
            status = self.posting_api.PostUpdate(event.source(), message)
            reply = "%s, I posted the following update: %s" % (nick, status.text)
        except IdenticaError:
            reply = "%s, text must be less than or equal to " % nick + \
                    "140 characters. Your text has length %d." % len(message)
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
    
    def do_command(self, event, cmd):
        nick = nm_to_n(event.source())
        conn = self.connection
        command = cmd.split()[0]
        if command == "help":
            pass
        elif command == "identify":
            tokens = cmd.split()
            if len(tokens) == 3:
                username = tokens[1]
                password = tokens[2]
                self.do_identify(conn, event, nick, username, password)
            else:
                reply = "%s, Usage 'identify <username> <password>'"
                if event.target() in self.channels.keys():
                    conn.privmsg(event.target(), reply)
                else:
                    conn.privmsg(nick, reply)
        elif command == "history":
            pass
        elif command == "post":
            self.do_post(conn, event, nick, cmd[len("post"):].strip())
        elif command == "reply":
            pass
        else:
            conn.notice(nick, "Unknown command: " + cmd)
    
    @staticmethod
    def get_mentions(conn, channel, posting_api, since_id):
        timestr = lambda sec: time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(sec)
            )
        while 1:
            time.sleep(10)
            statuses = posting_api.GetMentions(since_id)
            if len(statuses) > 0 and conn.socket != None:   # if there is a connection
                since_id = max([status.id for status in statuses])
                conf.identica.since_id = since_id
                for status in statuses:
                    mention = "@%s: %s (%s, %s)" % \
                            (status.user.screen_name,
                             status.text, 
                             timestr(status.created_at_in_seconds),
                             "https://identi.ca/notice/%d" % status.id
                            )
                    conn.privmsg(channel, mention)
    
    def start(self):
        try:
            SingleServerIRCBot.start(self)
        except BaseException:
            sys.stderr.write(traceback.format_exc())
            self.mention_grabber.terminate()
            exit(1)
        
