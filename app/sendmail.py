"""
Simple command line utility to send emails through an SMTP server.
"""

import os
import email
import email.utils
import email.mime.text
import smtplib

from typing import List


class BaseSendmail(object):

    def __init__(self, from_addr: str) -> None:
        self.smtp: smtplib.SMTP = None
        self.from_addr = from_addr

    def sendmail(self, to: List[str], msg: str, subject: str = None):
        if self.smtp is None:
            raise smtplib.SMTPException('need to authenticate first')
        mmsg = email.mime.text.MIMEText(msg, 'plain')
        mmsg['Subject'] = subject or '<no subject>'
        mmsg['From'] = self.from_addr
        mmsg['To'] = ', '.join(to)
        self.smtp.sendmail(self.from_addr, to, mmsg.as_string())

    def authenticate(self) -> None:
        pass

    def quit(self) -> None:
        self.smtp.quit()

class GMailMailer(BaseSendmail):

    def __init__(self, from_addr: str, user: str, password: str) -> None:
        super(GMailMailer, self).__init__(from_addr)
        self.user = user
        self.password = password
        self.authenticate()

    def authenticate(self):
        """
        Create a SMTP connection to a mail relaying server.

        Override this method in subclasses if some other
        authentication method is needed.
        """
        self.smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        self.smtp.login(self.user, self.password)


def mailer():
    """Use as:

    x = mailer()
    x.sendmail(['walter@waltermoreira.net'], 'hello5', subject='foo)

    """
    usr = os.environ['GMAIL_USER']
    pwd = os.environ['GMAIL_PASSWORD']
    from_ = os.environ['GMAIL_FROM']
    m = GMailMailer(from_, usr, pwd)
    return m
