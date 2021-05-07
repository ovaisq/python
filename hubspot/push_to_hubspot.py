#!/usr/bin/env python
"""
    BEFORE RUNNING THIS SCRIPT MAKE SURE YOU HAVE THE FOLLOWING INSTALLED:
        Python Requests Library
            pip install requests
        Python Dateutil Library
            pip install dateutil

        HAPI Key: this is the Developer Account KEY for Hubspot

    This tool does the following:
        Metabase to JSON (a manual export to JSON file)
            OR
        Metabase to JSON (using Metabase API)
            THEN
        Convert Metbase JSON to Hubspot Contact JSON
            THEN
        POST to Hubspot using Hubspot API

    CLI EXAMPLE 1:
    Metabase JSON is saved to a file:
        ./push_to_hubspot.py --file-json query_result_2018-04-13T04_13_32.319Z.json --hapi-key <hapi key> --root-json-key atlassian_technical_contact_email

    CLI EXAMPLE 2:
    Get Metabase JSON directly from METABASE API:
        ./push_to_hubspot.py --metabase-api-user <user> --metabase-api-pass <pass> 
            --metabase-query-json-url https://metabase.gliffy.net/api/card/131/query/json --hapi-key <hapi key> --root-json-key atlassian_technical_contact_email
"""

from datetime import datetime
from dateutil.parser import parse

import argparse
import calendar
import collections
import json
import requests
import sys
import time
import urlparse

def tstoepoch (ts):
    """UTC timestamp to UX Epoch time
        input: YYYY-MM-DDTHH:MM:SS.sss-HH:MM
               (e.g. 2018-04-11T00:00:00.000-05:00)
        output: 1523923200000

        Requires: dateutil library
    """

    if ts:
        # python 2.7 does not support %z (-05:00) timezone info
        # so have to use parse to convert ts to a datetime.datetime obj
        dtobjiso = parse(ts) # returns datetime.datetime(2018, 4, 11, 0, 0, tzinfo=tzoffset(None, -18000))
        # timestamp obj in EPOCH
        timestampobj = calendar.timegm(dtobjiso.timetuple()) # returns 1523404800
        # time tuple in UTC
        dtobjutc = datetime.fromtimestamp(timestampobj) # returns datetime.datetime(2018, 4, 10, 17, 0)
        # EPOCH in ms
        epochms = (int((time.mktime(dtobjutc.timetuple())) + 0.5) * 1000) # returns 1523404800000

        return epochms
    else:
        return ts

def utcwithepoch(jsondict, k, v):
    """Replace UTC timestamp with Epoch timestamp in list of python dictionaries
    """

    for key in jsondict.keys():
        if key == k:
            jsondict[key] = v
        elif type(jsondict[key]) is dict:
            utcwithepoch(jsondict[key], k, v)

def tojsonobj(json_file_name, metabase_query_json_url, x_metabase_session_id):
    """Read in Metabase JSON output, and prepare it for POST to Hubspot
        Replace UTC timestamps with EPOCH timestamps

        TODO: Create either an API key or a dedicated user/pass for API access
              in metabase.gliffy.net instance. Perhaps have this baked into
              all Metabase instances.
    """

    if json_file_name:
        jsonobj = json.loads(open(json_file_name,'r').read())
    else:
        # read it directly from metabase
        metabase_headers = {'X-Metabase-Session': x_metabase_session_id}
        # predefined metabase query
        jsonobj = json.loads(http_post(metabase_query_json_url, None, None, metabase_headers))

    for adict in jsonobj:
        for akey in adict.keys():
            if '_date' in akey:
                utcwithepoch(adict, akey, tstoepoch(adict[akey]))

    return jsonobj

def getmetabasesessionid (root_url, api_user, api_pass):
    """Get Metabase Session id
    """

    # metabase session api route
    session_route = '/api/session/'

    # post header
    appjson_post_headers = {'Content-Type' : 'application/json'}

    # session id post data
    session_id_data = {
                       'username' : api_user
                        ,'password' : api_pass
                      }

    # returns json object {"id" : <uuid>}
    session_id_resp = http_post(root_url + session_route, None, json.dumps(session_id_data), appjson_post_headers)

    # return just the session id
    try:
        session_id = json.loads(session_id_resp)['id']
        return session_id
    # handle metabase login rate limiting
    except KeyError, e:
        print session_id_resp
        sys.exit(-1)
        

def hubspotjson(ajsonobj, rootjsonkey):
    """Roll the Metabase JSON into Hubspot "properties" key

        Sample BEFORE:
          {
            "atlassian_technical_contact_address_2": "",
            "atlassian_technical_contact_email": "nobody@gmail.com",
            "atlassian_technical_contact_city": "",
            "confluence_eval_start_date": "2018-04-11T00:00:00.000-05:00",
            "confluence_edition": "Evaluation",
            "atlassian_technical_contact_state": "",
            "confluence_license_id": "SEN-L99",
            "confluence_eval_end_date": "2018-05-11T00:00:00.000-05:00",
            "confluence_add_on_name": "Confluence",
            "atlassian_technical_contact_address_1": "",
            "atlassian_technical_contact_phone": "",
            "atlassian_organisation_name": "Telconet",
            "confluence_license_type": "EVALUATION",
            "confluence_add_on_key": "com.integration.confluence",
            "atlassian_technical_contact_name": "JF",
            "atlassian_technical_contact_country": "EC",
            "atlassian_billing_contact_email": "",
            "atlassian_billing_contact_phone": "",
            "atlassian_technical_contact_postcode": "",
            "atlassian_billing_contact_name": ""
          }

        Sample AFTER:
            {
            'email':'nobody@gmail.com',
            'properties': [{
                    'property':'confluence_license_type',
                    'value':'EVALUATION'
            }, {
                    'property':'confluence_license_id',
                    'value':'SEN-L99'
            }, {
                    'property':'atlassian_technical_contact_country',
                    'value':'EC'
            }, {
                    'property':'atlassian_organisation_name',
                    'value':'Te'
            }, {
                    'property':'atlassian_technical_contact_address_1',
                    'value':''
            }, {
                    'property':'confluence_edition',
                    'value':'Evaluation'
            }, {
                    'property':'confluence_eval_end_date',
                    'value': '3220000'
            }, {
                    'property':'atlassian_technical_contact_phone',
                    'value':''
            }, {
                    'property':'atlassian_technical_contact_address_2',
                    'value':''
            }, {
                    'property':'confluence_add_on_key',
                    'value':'com.integration.confluence'
            }, {
                    'property':'atlassian_billing_contact_name',
                    'value':''
            }, {
                    'property':'atlassian_billing_contact_email',
                    'value':''
            }, {
                    'property':'confluence_add_on_name',
                    'value':'Confluence'
            }, {
                    'property':'atlassian_technical_contact_name',
                    'value':'JF'
            }, {
                    'property':'confluence_eval_start_date',
                    'value': '392320'
            }, {
                    'property':'atlassian_technical_contact_postcode',
                    'value':''
            }, {
                    'property':'atlassian_technical_contact_city',
                    'value':''
            }, {
                    'property':'atlassian_technical_contact_state',
                    'value':''
            }, {
                    'property':'atlassian_billing_contact_phone',
                    'value':''
            }
        ]
        }

    """

    # init dicts and lists
    contactjsonobj = {}
    propertyjsonobj = {}
    properties = []
    contacts = []

    # using metabase JSON build up a blob of contact JSON for Hubspot
    for acontact in ajsonobj:
        for akey in acontact.keys():
            # build contact JSON for a given e-mail for hubspot
            if akey != rootjsonkey:
                propertyjsonobj['property'] = akey
                propertyjsonobj['value'] = acontact[akey]
                properties.append(propertyjsonobj)
            propertyjsonobj = {}
        try:
            contactjsonobj['email'] = acontact[rootjsonkey]
            contactjsonobj['properties'] = properties
            contacts.append((contactjsonobj))
            properties = []
            contactjsonobj = {}
        except KeyError, e:
            print 'ERROR:',rootjsonkey,'key not found!'
            sys.exit(-1)

        # this breaks at 1 - leaving it here for debugging
        # break

    return contacts

def geturlroot(url):
    """Extract root url from a multipath url
    """
    # extract just the root url from JSON query URL
    urlroot = urlparse.urlparse(url).scheme + '://' + urlparse.urlparse(url).netloc
    return urlroot

def validatejson(jsonblob):
    """Validate whether a string blob is JSON
    """

    try:
        json_object = json.loads(jsonblob)
    except ValueError, e:
        return False
    except TypeError, e:
        return False
    return True

def prepareresponse(http_request_response):
    """Prepare http response - based on response return
        either text or JSON
    """

    if http_request_response.text:
        if validatejson(json.dumps(http_request_response.json())):
            print 'JSON'
            return json.dumps(http_request_response.json(), indent=4)
        else:
            print 'TEXT'
            return http_request_response.text
    else:
        http_request_response = 'INFO: Empty String Returned'
        return http_request_response

def http_post (url, params, post_data, headers):
    """http post generalized
    """

    resp = requests.post(url, data=post_data, headers=headers, params=params)

    if resp.status_code >= 400:
        print 'ERROR: Something bad happend to your post to', url
        print 'ERROR: Status Code Returned:', resp.status_code
        print resp.text
    else:
        print 'INFO: Post to', url
        print 'INFO: Request successful!', resp.status_code

    return prepareresponse(resp)

if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(prog='push_to_hubspot.py', description='Create Contacts in Hubspot')

    arg_parser.add_argument(
                            '--properties-json'
                            , dest='properties_json_file'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Metabase exported Json'
                            )
    arg_parser.add_argument(
                            '--file-json'
                            , dest='file_json'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Metabase exported Json'
                            )
    arg_parser.add_argument(
                            '--metabase-api-user'
                            , dest='metabase_api_user'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Metabase API User - Ask DevOps'
                            )
    arg_parser.add_argument(
                            '--metabase-api-pass'
                            , dest='metabase_api_pass'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Metabase API password - Ask DevOps'
                            )
    arg_parser.add_argument(
                            '--hapi-key'
                            , dest='hapi_key'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Hubspot API Key - required to post to Hubspot'
                            )
    arg_parser.add_argument(
                            '--metabase-query-json-url'
                            , dest='metabase_query_json_url'
                            , action='store'
                            , required=False
                            , default=''
                            , help="Metabase Query/Card JSON output URL\n"
                                    "e.g. https://metabase.gliffy.net/api/card/131/query/json"
                            )
    arg_parser.add_argument(
                            '--root-json-key'
                            , dest='root_json_key'
                            , action='store'
                            , required=False
                            , default=''
                            , help='Root JSON Key to build the Hubspot JSON around'
                            )

    args = arg_parser.parse_args()
   
    # read properties from a file
    if args.properties_json_file:
        properties_file = args.properties_json_file
        properties_json = json.loads(open(properties_file,'r').read())
        if any(properties_json.values()):
            file_json = properties_json['file_json']
            hapi_key = properties_json['hapi_key']
            metabase_query_json_url = properties_json['metabase_query_json_url']
            metabase_api_user = properties_json['metabase_api_user']
            metabase_api_pass = properties_json['metabase_api_pass']
            root_json_key = properties_json['root_json_key']
        else:
            print 'Empty Properties File'
            sys.exit(-1)
    else:
        if any(vars(args).values()):
            # command line args to local vars
            file_json = args.file_json
            hapi_key = args.hapi_key
            metabase_query_json_url = args.metabase_query_json_url
            metabase_api_user = args.metabase_api_user
            metabase_api_pass = args.metabase_api_pass
            root_json_key = args.root_json_key
        else:
            print 'Missing Args'
            arg_parser.print_help()
            sys.exit(-1)

    # metabase root url
    metabase_root_url = geturlroot(metabase_query_json_url)

    # hubspot api key
    hapi_params = {'hapikey' : hapi_key}
    # hubspot BATCH api url
    hubspotbatch_api_url = 'https://api.hubapi.com/contacts/v1/contact/batch/'

    # transform metabase JSON into Hubspot POST compliant JSON
    hubspotcontacts = hubspotjson(tojsonobj(file_json, metabase_query_json_url, getmetabasesessionid(metabase_root_url, metabase_api_user, metabase_api_pass)), root_json_key)

    # hubspot POST api header2
    ct_appjson_post_headers = {'Content-Type' : 'application/json'}

    # Hubspot batch post supports 1000 contacts at a time - split the contacts in
    #   batches of 900 if total is = or greater than 1000
    # source: https://developers.hubspot.com/docs/methods leaving it here for debugging/contacts/batch_create_or_update

    if (len(hubspotcontacts) >= 1000):
        print 'INFO: Batching to Hubspot'
        batch = 900
        listoflists = [hubspotcontacts[i:i+batch] for i in range(0, len(hubspotcontacts), batch)]
        # post batches
        print 'Total items', len(hubspotcontacts)
        numsublists = len(listoflists)
        for sublist in listoflists:
            print 'INFO:',listoflists.index(sublist)+1,'of', numsublists, 'with each list containing', len(sublist)
            http_post(hubspotbatch_api_url, hapi_params, json.dumps(sublist), ct_appjson_post_headers)
    else:
        hubspot_response = http_post(hubspotbatch_api_url, hapi_params, json.dumps(hubspotcontacts), ct_appjson_post_headers)
        # posts with 201,202,203,204 returns no text
        print 'INFO: Hubspot response:', hubspot_response
