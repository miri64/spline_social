#!/usr/bin/env python
# coding=utf-8
import getpass, sys
from xmlrpclib import ServerProxy

def register():
    rpc = ServerProxy("http://localhost:9000/")
    uid = getpass.getuser()
    username = raw_input(u"Dein Spline-Username [%s]: " % uid)
    spline_username = uid if username == '' else username
    spline_password = getpass.getpass('Dein LDAP-Passwort: ')
    username = raw_input(u"Waehle deinen Benutzernamen fuer den IRC-Bot [%s]: " % spline_username)
    irc_username = uid if username == '' else username
    irc_password = 0
    irc_password2 = 1
    while irc_password != irc_password2:
        irc_password = getpass.getpass(u'Waehle ein Passwort fuer die Anmeldung: ')
        irc_password2 = getpass.getpass('Wiederholung: ')
        if irc_password != irc_password2:
            print u"Passwoerter stimmen nicht ueberein."
    print "Willst du per Mail (%s@spline.inf.fu-berlin.de) informiert werden, wenn du einen Post schreibst? [y/N] " % spline_username,
    get_mail_char = sys.stdin.read(1)
    if get_mail_char.lower() == 'y':
        get_mail = True
    else:
        get_mail = False
    success = rpc.add_user(spline_username, spline_password, irc_password, irc_username, get_mail)
    if success:
        print "Anmeldung erfolgreich."
    else:
        print "Anmeldung fehlgeschlagen. Spline-Credentials falsch?"
    
if __name__ == '__main__':
    register()
