import configparser
import json
import requests

from twilio.rest import Client

# pip3 install -r requirements.txt

class TwilioHelper(object):

    def __init__(self):

        #read config from twilio.config file
        self.config = configparser.RawConfigParser()
        self.config.read('twilio.config')
        self.tw_sid = self.config.get('twilio_sms','sid')
        self.tw_token = self.config.get('twilio_sms','auth')
        self.tw_from_ = self.config.get('twilio_sms','from')
        self.phone_validate_api_key = self.config.get('abstract_api','key')
        self.phone_validate_api_url = self.config.get('abstract_api','api_url')

        self._client = Client(self.tw_sid, self.tw_token)

    def sendsms(self, send_to, send_text):
        """Send SMS"""

        self.to = send_to
        self.valid = self.validatephone(send_to)
        if self.valid:
            self.body = send_text
            self.message = self._client.messages.create(
                                                        to=self.to,
                                                        from_=self.tw_from_,
                                                        body=self.body
                                                    )
            self.sid = self.message.sid
            self.message_status = self._client.messages(self.sid).fetch().status
            while (self.message_status == 'sent'):
                self.message_status = self._client.messages(self.sid).fetch().status
        else:
             self.message_status = 'Destination Phone Number '
             self.message_status += send_to
             self.message_status += ' is invalid. Please Try again'
             return self.message_status

    def validatephone(self, send_to):
        """Validate Phone Number

        Using Abstract Phone Validation API
            https://app.abstractapi.com/api/phone-validation
        """

        self.send_to = send_to.lstrip('+')
        self.params = {
                       'api_key': self.phone_validate_api_key,
                       'phone' : self.send_to
                      }
        response = requests.get(self.phone_validate_api_url,params=self.params)
        decoded_content = json.loads(response.content.decode('UTF-8'))
        is_phonenumber_valid = decoded_content['valid']

        return is_phonenumber_valid


