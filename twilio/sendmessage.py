#!/usr/bin/env python3
"""Send a message using Twilio

Example:
    Unhappy path
        ./sendmessage.py --send-sms-to +1714555
        Message Status: Destination Phone Number +1714555 is invalid. Please Try again

    Happy Path
        ./sendmessage.py --send-sms-to +17145551212
        Message Status: delivered
"""

import argparse
import json
import logging
import os
import sys

from pathlib import Path
from twiliohelper import TwilioHelper as twilio

def main():

    log_filename = Path(os.path.basename(__file__)).with_suffix('.log')
    logging.basicConfig(filename=log_filename, level=logging.INFO)

    arg_parser = argparse.ArgumentParser(description="Twilio Messaging Tool")
    arg_parser.add_argument (
                             '--send-sms-to',
                             dest='send_sms_to',
                             action='store',
                             default='+17145551212',
                             help="Send SMS Phone Number +17145551212",
                            )
    arg_parser.add_argument (
                             '--send-sms-msg',
                             dest='send_sms_msg',
                             action='store',
                             default='Hello!',
                             help="SMS Message Body",
                            )

    args = arg_parser.parse_args()
    send_sms_to = args.send_sms_to
    send_sms_msg = args.send_sms_msg

    #instantiate twilio    
    tw = twilio()

    if send_sms_to:
        message_info = tw.sendsms(send_sms_to,send_sms_msg)
        print ('Message Status:',message_info)
    else:
        print (arg_parser.print_help(sys.stderr))

if __name__ == "__main__":
    main()
