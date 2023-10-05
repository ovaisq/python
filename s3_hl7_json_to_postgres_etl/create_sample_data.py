#!/usr/bin/env python3
""" Generate Sample files
"""


import random
from random import randrange
from random_word import RandomWords
from multiprocessing import Process
import datetime
from faker import Faker
import json
import redis
import uuid

redishost=<redis host name/ip>
redisport=6379

R = redis.Redis(host=redishost, port=redisport, decode_responses=True)

US_STATES = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
GENDER = ['M','F']

def main():
    num_files = 200000
    for i in range(num_files):
        pid = str(randrange(1000000,9999999))
        filename = 'pid_'+pid+'_'+uuid.uuid4().hex+".json"

        fake = Faker()
        updatedat = fake.date_time_between(start_date='-2y', end_date='now').strftime("%Y-%m-%d %H:%M")
        dob = fake.date_time_between(start_date='-40y', end_date='-10y').strftime("%Y-%m-%d")
        dobint = dob.replace('-','')
        name = fake.name().split(' ')
        rnfname = name[0].upper()
        rnlname = name[-1].upper()
        name = fake.name().split(' ')
        pfname = name[0].upper()
        plname = name[-1].upper()


        r = RandomWords()
        tenantid = r.get_random_word()

        visitnum = str(randrange(10000000,99999999))
        somecode = 'S'+str(randrange(10000,99999))
        

        sample = {
          "patientId": pid,
          "tenantId": tenantid,
          "dob": dob,
          "id": pid,
          "updatedAt": updatedat,
          "createdAt": updatedat,
          "visitNumber": visitnum,
          "MSH": "MSH|^~&|EPICCARE|WB^WBPC|||20230110144357|"+somecode+"|ADT^A08^ADT_A01|400815517|P|2.3",
          "EVN": "EVN|A08|20230110144357||REGCHECKCOMP_A08|"+somecode+"^"+rnlname+"^"+rnfname+"^ANAME^^^^^WB^^^^^WBPC||WBPC^1740348929^SOMENAME",
          "PID": "PID|1||14891584^^^^EPI~62986117^^^^SOMERN||"+pfname+"^"+plname+"||"+dobint+"|"+random.choice(GENDER)+"|||123 MAIN ST^^SAN CITY^"+random.choice(US_STATES)+"^12345^USA^P^^SC",
          "PV1": "PV1|||WBPCIVTA^^^WBPC^^^WBPC^^WBPC INFUSION THERAPY||||||||||||||||1219753048"
        }

        #with open('sample_jsons/'+filename,"w") as json_file:
        #    #json_file.write(json.dumps(sample))
        #    json.dump(json.loads(json.dumps(sample)), json_file)
        R.json().set(filename, '$', json.dumps(sample))

if __name__ == '__main__':
    p1 = Process(target=main)
    p2 = Process(target=main)
    p3 = Process(target=main)
    p4 = Process(target=main)

    p1.start()
    p2.start()
    p3.start()
    p4.start()

    p1.join()
    p2.join()
    p3.join()
    p4.join()
