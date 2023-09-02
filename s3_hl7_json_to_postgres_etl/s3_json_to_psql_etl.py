#!/usr/bin/env python3
"""Script that processes HL7 data from JSON files stored in S3 buckets
    and stores the transformed/processed data in PostgreSQL schema.
   See README.md for more details
    TODO: add logger
"""

import argparse
import configparser
import sys
import time
from ast import literal_eval as make_tuple
from datetime import datetime
from hl7apy.parser import parse_segment, parse_field
from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException

# Constants
IGNORE_SEG_FIELDS = ['PID_1', 'PID_12','PV1_1', 'IN1_1', 'EVN_1','OBX_1', 'AL1_1', 'GT1_1', 'DG1_1']
IGNORE_COMPONENT_FIELDS = [
                           'CX_4',
                           'CX_5',
                           'XTN_2',
                           'XTN_3',
                           'XTN_5',
                           'XTN_6',
                           'XTN_7',
                           'XCN_4',
                           'XPN_3'
                          ]

#TODO: make this an arg supplied value
S3BUCKETPREFIX = '<s3_bucket_name>/2023/08/28'

#TODO: perhaps push it into a config file
HL7_SEGMENTS = [
                'pid',
                'pv1',
                'pv2',
                'pd1',
                'evn',
                'in1',
                'in2',
                'obx',
                'al1',
                'gt1',
                'zpv',
                'dg1',
                'nk1'
                ]

# transformed fields to ignore
with open('hl7_field_names_to_ignore.txt', encoding='utf-8') as afile:
    IGNORE_FIELDS = [line.rstrip('\n') for line in afile]

def date_to_prefix():
    """for lambda version - use this prefix to pick most recent
        json dump from mirth into s3 buckets
    """

    date_prefix = '/' + datetime.today().strftime('%Y/%-m/%-d')
    return date_prefix

def read_config(file_path):
    """ read config file
    """

    config_obj = configparser.RawConfigParser()
    config_obj.read(file_path)
    return config_obj

def get_s3_jsons(sparksession, s3_bucket_prefix):
    """ get all jsons
    """
    try:
        a_d_f = sparksession.read.option("multiline","true") \
                .json("s3a://" + s3_bucket_prefix).dropDuplicates()
        return a_d_f
    except AnalysisException:
        print ("Unable to read JSON files at", s3_bucket_prefix)
        sys.exit(-1)

def ac_names(sgchild):
    """ segment children names
    """

    if sgchild.name is None:
        short_name = "None"
    else:
        short_name = sgchild.name
    if sgchild.long_name is None:
        long_name = "None"
    else:
        long_name = sgchild.long_name
    return short_name.lower(), long_name.lower()

def process_data(json_df, segments):
    """Parse HL7 raw data - extract values for segments and associated fields, create a dictionary.
        Add dictironay to list of dictionarties.
    """

    parsed_data = []

    for adict in json_df.collect():
        data_dict = {
            'patientid': adict['patientid'],
            'dob': adict['dob']
        }

        for s_g in segments:
            try:
                adict[s_g]
            except (KeyError, ValueError):
                continue

            asegment = parse_segment(adict[s_g])

            for achild in asegment.children:
                ac_name, ac_long_name = ac_names(achild)

                if ac_name.upper() not in IGNORE_SEG_FIELDS:
                    field = parse_field(achild.value, name=achild.name)

                    for fchild in field.children:
                        if fchild.name.upper() not in IGNORE_COMPONENT_FIELDS:
                            fc_name, fc_long_name = ac_names(fchild)
                            field_name = f'{ac_name}_{ac_long_name}_{fc_name}_{fc_long_name}'

                            if field_name not in IGNORE_FIELDS:
                                data_dict[field_name] = fchild.value
        parsed_data.append(data_dict)

    return parsed_data

def rename_df_columns(data_frame):
    """read (orig, new) tuples from a file into list of tuples
        rename columns to more readable format
    """

    with open("field_map.txt", encoding='utf-8') as field_map_file:
        rename_map = field_map_file.readlines()

    for arow in rename_map:
        atuple = make_tuple(arow)
        orig = atuple[0]
        new = atuple[-1]
        data_frame = data_frame.withColumnRenamed(orig, new)

    return data_frame

def truncate_col_name(a_df):
    """catch column names that are greater than 63 bytes
        truncate them for postgres
    """

    for col_name in a_df.columns:
        size_bytes = len(col_name.encode('utf-8'))
        if size_bytes > 63:
            print ('Long column name',col_name)
            truncated  = col_name[:62]
            print ('Truncated column name',truncated)
            a_df = a_df.withColumnRenamed(col_name, truncated)
    return a_df

def lower_case_col_names(a_df):
    """lower case column names
    """

    a_df = a_df.toDF(*[c.lower() for c in a_df.columns]) #lowercase column names
    return a_df

def df_to_jdbc(a_df, adtfeed):
    """jdbc processed df into postgres
    """

    config_obj = read_config('etl.config')
    dbhost = config_obj.get('reportdb','host')
    dbport = config_obj.get('reportdb','port')
    dbname = config_obj.get('reportdb','dbname')
    dbuser = config_obj.get('reportdb','dbuser')
    dbuserpass = config_obj.get('reportdb','dbuserpass')

    # no - in tablename...
    datamodel_ver = 'v4'
    tablename = datamodel_ver + '_' + adtfeed.replace('-','_')

    url = "jdbc:postgresql://"+dbhost+":"+dbport+"/"+dbname
    properties = {
                    "user": dbuser,
                    "password": dbuserpass,
                    "driver": "org.postgresql.Driver",
                    "batchsize" : "2000"
                    }
    try:
        # mode("ingore") is just NOOP if table (or another sink) already exists
        #  and writing modes cannot be combined. If you're looking for something
        #  like INSERT IGNORE or INSERT INTO ... WHERE NOT EXISTS ... 
        #  you'll have to do it manually - so append it is
        a_df.write.jdbc(url, tablename, mode="append", properties=properties)
        print ("**** Stored data in table", tablename)
        return True
    except AnalysisException as e_error:
        print (e_error)
        sys.exit(-1)

def df_etl(sparksession, adtfeedname, segments, s3bucketprefix):
    """Apache Spark Magic happens here
    """

    df_jsons = ''
    transformed = ''
    df_transformed = ''

    df_jsons = get_s3_jsons(sparksession, s3bucketprefix)
    df_jsons = lower_case_col_names(df_jsons)

    # process HL7 segments
    transformed = process_data(df_jsons, segments)
    d_f = sparksession.createDataFrame(spark.sparkContext.parallelize(transformed))

    df_transformed = rename_df_columns(d_f)

    df_transformed.createOrReplaceTempView("patients")
    sql_query = "select * from patients where \
                pt_address_state_prov in ('CA', 'OR', 'WA', 'ID', 'UT')"
    try:
        df_transformed = sparksession.sql(sql_query)
    except AnalysisException as e_error:
        print ("Query Failed", e_error)
        sys.exit(-1)

    # don't go any further if DF is empty
    if df_transformed.count() < 1:
        print ('Skipping Empty dataframe',df_transformed.count())
        sys.exit(-1)

    df_transformed = truncate_col_name(df_transformed)
    df_to_jdbc(df_transformed, adtfeedname)
    df_transformed = ''

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Process JSON to PostgreSQL")
    arg_parser.add_argument (
                             '--adt-feed-name',
                             dest='adt_feed_name',
                             action='store',
                             default='',
                             required='true',
                             help="Single value or comma separated, \
                                    Feed name i.e. adt_feed1 or adt_feed1,adt_feed2",
                            )

    args = arg_parser.parse_args()
    # since I had to deal with several adt feeds, I chose to
    #  do it this way.
    adt_feed_name = args.adt_feed_name

    config = read_config('etl.config')
    spark_master = config.get('spark', 'master')
    spark_master_port = config.get('spark', 'masterport')
    aws_access_key = config.get('aws','access.key')
    aws_secret_key = config.get('aws','secret.key')

    spark = (SparkSession.builder
             .appName('adt_feed' + '_' + adt_feed_name + '_' + str(int(time.time())))
             .master(f"spark://{spark_master}:{spark_master_port}")
             .config("spark.executor.memory", "14g")
             .config("spark.executor.cores", "4")
             .config("spark.task.cpus", "4")
             .config("spark.sql.debug.maxToStringFields", "25")
             .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
             .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
             .config("spark.jars",
                        "/var/tmp/sparkjars/postgresql-42.6.0.jar,\
                         /var/tmp/sparkjars/aws-java-sdk-bundle-1.12.262.jar,\
                         /var/tmp/sparkjars/hadoop-aws-3.3.4.jar")
             .getOrCreate())


    # can pass more than one name
    for adt_feed_name in adt_feed_name.split(','):
        print ("**** Starting for", adt_feed_name)
        df_etl(spark, adt_feed_name, HL7_SEGMENTS, S3BUCKETPREFIX)
        print ("**** Completed for", adt_feed_name)

    spark.stop()
