import random, os
from datetime import datetime
from apicalls import IdenticaError
from itertools import chain

def random_str(max_len = 30,with_ws=True):
    sample = './&%$!?\'"12345678890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    if with_ws:
        sample += '\t\n '
    return unicode(''.join( 
            map(
                    lambda x:
                            sample[ord(x)%len(sample)], 
                    os.urandom(random.choice(range(1,max_len)))
            )
        ))

class User(object):
    def __init__(self):
        self.screen_name = random_str(with_ws=False)

class Status(object):
    def __init__(self):
        self.id = random.randint(0, (2**32)-1)
        self.created_at_in_seconds = random.randint(0, (2**32)-1)
        self.created_at = datetime.fromtimestamp(
                self.created_at_in_seconds
            ).strftime("%Y-%m-%d %H:%M:%S")
        self.text = random_str(140)
        self.user = User()

class DummyApi(object):
    def __init__(self, start_posts = 10):
        self.posts = [Status() for _ in range(start_posts)]
    
    def add_post(self,post):
        self.posts.append(post)
    
    def GetMentions(self,since_id):
        c = [post for post in self.posts if post.id > since_id]
        return random.population(c,random.choice(0,len(c)))
    
    def GetStatus(self,status_id):
        c = [post for post in self.posts if post.id == status_id]
        if len(c) > 0:
            return c[0]
        else:
            raise IdenticaError('')

class Event(object):
    def __init__(self, source, target):
        self._source = source
        self._target = target
    
    def source(self):
        return self._source
    
    def target(self):
        return self._target

class Connection(object):
    def __init__(self, nickname):
        self.priv_msgs = {}
        self.nickname = nickname
    
    def privmsg(self, target, msg):
        if self.priv_msgs.get(target) == None:
            self.priv_msgs[target] = []
        self.priv_msgs[target] += [unicode(msg.strip())]
    
    def get_nickname(self):
        return self.nickname
    
    def got_message(self, msg):
        return unicode(msg.strip()) in self.get_all_msgs()
    
    def get_all_msgs(self):
        return list(chain(*self.priv_msgs.values()))
    
    def empty_msgs(self):
        self.priv_msgs = {}
