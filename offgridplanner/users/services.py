"""
This module is utilized primarily during user registration in the application to send activation links. It is also used
for sending password reset emails or notifications for changes in user email. Additionally, the module is employed to
dispatch emails upon the completion of project calculations, provided the user has enabled email notifications.
Moreover, it serves a critical function in error logging by sending relevant email alerts.
"""

import os
import smtplib
import warnings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_mail(to_address, msg, subject="Activate your PeopleSun-Account"):
    smtp_server = os.environ.get("MAIL_HOST")
    smtp_port = os.environ.get("MAIL_PORT")
    smtp_username = os.environ.get("MAIL_ADDRESS")
    smtp_password = os.environ.get("MAIL_PW")
    message = MIMEMultipart()
    message["From"] = os.environ.get("HEADER_ADDRESS")
    message["To"] = (
        to_address if "@" in to_address else os.environ.get("MAIL_ADDRESS_LOGGER")
    )
    message["Subject"] = subject
    message.attach(MIMEText(msg, "plain"))
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        try:
            server.login(smtp_username, smtp_password)
            server.sendmail(
                os.environ.get("MAIL_ADDRESS"),
                message["To"],
                message.as_string(),
            )
        except smtplib.SMTPAuthenticationError as e:
            print("\n{}\n{}".format(e, os.environ.get("MAIL_ADDRESS").replace("@", "")))
            warnings.warn(str(e), category=UserWarning, stacklevel=2)
