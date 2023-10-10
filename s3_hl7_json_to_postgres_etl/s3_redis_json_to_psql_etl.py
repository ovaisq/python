#!/usr/bin/env python3
"""Script that processes HL7 data from JSON files stored in S3 buckets
    and stores the transformed/processed data in PostgreSQL schema.
   See README.md for more details
    TODO: add logger
"""

import ast
import argparse
import configparser
import logging
from datetime import datetime
import sys
import time
from ast import literal_eval as make_tuple
from hl7apy.parser import parse_segment, parse_field
from py4j.protocol import Py4JJavaError
from pyspark.sql import SparkSession
from pyspark.sql.utils import AnalysisException, ParseException
import psycopg2
import redis
import numpy

# transformed fields to ignore
with open('hl7_field_names_to_ignore.txt', encoding='utf-8') as afile:
    IGNORE_FIELDS = [line.rstrip('\n') for line in afile]

# Constants
STATES = ['CA', 'OR', 'WA', 'ID', 'UT']

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

def get_s3_jsons(sparksession, s3_full_path):
    """ get all jsons
    """
    try:
        a_d_f = sparksession.read.json('s3a://' + s3_full_path, multiLine=True).dropDuplicates()
        return a_d_f
    except (AnalysisException, ParseException, Py4JJavaError):
        logging.error('Unable to read JSON files at %s', s3_full_path)
        sys.exit(-1)

def get_redis_jsons(redishost, redisport):
    """Read JSON files from RedisJSON doc store
        expects key names starting with "pid_"

        Tested this against RedisJSON/Redis-Stack-Server v7.2.0
    """

    jsons = []

    r_edis = redis.Redis(host=redishost, port=redisport, decode_responses=True)

    #get keys as list
    search_for = 'pid_121*'

    logging.info('**** Getting following RedisJSON keys: %s ****', search_for)

    json_keys = list(r_edis.scan_iter(search_for))

    for ajson in json_keys:
        a_json = r_edis.json().get(ajson)
        jsons.append(a_json)

    adf = spark.read.json(spark.sparkContext.parallelize(jsons,numSlices=840) \
            , multiLine=True).dropDuplicates()

    return adf

def df_to_dict_batches(json_df):
    """Break list of dicts into smaller chunks
        speeds up data processing
    """

    logging.info('**** Json DF to Dict  ****')
    dicts = json_df.toPandas().to_dict('records')
    dicts_batches = numpy.array_split(dicts, 100)

    return dicts_batches

def assign_child_name(sgchild):
    """ assign child names
    """

    short_name = "None" if sgchild.name is None else sgchild.name
    long_name = "None" if sgchild.long_name is None else sgchild.long_name

    return short_name.lower(), long_name.lower()

def process_hl7_segment(hl7_segment, json_dict, new_data_dict):
    """
    Parse HL7 raw data to extract values for segments and associated fields and create a dictionary.
    Add the dictionary to a list of dictionaries.
    """

    try:
        segment_data = json_dict.get(hl7_segment)
        if not segment_data:
            return False

        asegment = parse_segment(segment_data)
        for achild in asegment.children:
            ac_name, ac_long_name = assign_child_name(achild)
            if ac_name.upper() in IGNORE_SEG_FIELDS:
                continue

            field = parse_field(achild.value, name=achild.name)
            for fchild in field.children:
                if fchild.name.upper() in IGNORE_COMPONENT_FIELDS:
                    continue

                fc_name, fc_long_name = assign_child_name(fchild)
                field_name = f'{ac_name}_{ac_long_name}_{fc_name}_{fc_long_name}'
                if field_name not in IGNORE_FIELDS:
                    new_data_dict[field_name] = fchild.value
        return new_data_dict
    except (TypeError, KeyError, ValueError):
        return False

def process_data(dict_batch, segments, sparksession):
    """process HL7 data - filter STATES
    """
    parsed_data = []

    logging.info('**** Start Processing HL7 ****')

    for adict in dict_batch:

        data_dict = {
            'patientid': adict['patientid'],
            'dob': adict['dob']
        }

        for s_g in segments:
            if not process_hl7_segment(s_g, adict, data_dict):
                continue
            data_dict = process_hl7_segment(s_g, adict, data_dict)

        # filter out STATES
        if data_dict['pid_11_patient_address_xad_4_state_or_province'] in STATES:
            parsed_data.append(data_dict)
    if parsed_data:
        logging.info('**** Creating DF ****')
        a_d_f = sparksession.createDataFrame(parsed_data)
        a_d_f = rename_df_columns(a_d_f)
        return a_d_f

    logging.info('**** Empty DF ****')
    return False

def rename_df_columns(data_frame):
    """read (orig, new) tuples from a file into list of tuples
        rename columns to more readable format
    """

    logging.info('**** Rename Column Names ****')
    with open('field_map.txt', encoding='utf-8') as field_map_file:
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

    logging.info('**** Truncate Column Names ****')
    for col_name in a_df.columns:
        size_bytes = len(col_name.encode('utf-8'))
        if size_bytes > 63:
            logging.info('Long column name %s', col_name)
            truncated  = col_name[:62]
            logging.info('Truncated column name %s', truncated)
            a_df = a_df.withColumnRenamed(col_name, truncated)
    return a_df

def lower_case_col_names(a_df):
    """lower case column names
    """

    logging.info('**** Lowercase Column Names ****')
    a_df = a_df.toDF(*[c.lower() for c in a_df.columns]) #lowercase column names
    return a_df

def df_to_jdbc(a_df, adtfeed):
    """jdbc processed df into postgres
    """

    logging.info('**** Adding rows to PostgreSQL ****')
    config_obj = read_config('etl.config')
    dbhost = config_obj.get('reportdb','host')
    dbport = config_obj.get('reportdb','port')
    dbname = config_obj.get('reportdb','dbname')
    dbuser = config_obj.get('reportdb','dbuser')
    dbuserpass = config_obj.get('reportdb','dbuserpass')

    # no - in tablename...
    datamodel_ver = 'v5'
    tablename = datamodel_ver + '_' + adtfeed.replace('-','_')

    url = 'jdbc:postgresql://'+dbhost+':'+dbport+'/'+dbname
    properties = {
                    'user': dbuser,
                    'password': dbuserpass,
                    'driver': 'org.postgresql.Driver',
                    'batchsize' : '2000'
                    }
    try:
        # mode("ingore") is just NOOP if table (or another sink) already exists
        #  and writing modes cannot be combined. If you're looking for something
        #  like INSERT IGNORE or INSERT INTO ... WHERE NOT EXISTS ...
        #  you'll have to do it manually - so append it is
        a_df.write.jdbc(url, tablename, mode='append', properties=properties)
        logging.info('**** Stored %s rows in table %s', str(a_df.count()), tablename)
        return True
    except AnalysisException as e_error:
        if "not found in schema" in str(e_error):
            p_config = read_config('etl.config')
            _, psql_cursor = psql_connection(p_config)
            create_table (tablename, a_df.columns, psql_cursor)
            a_df.write.jdbc(url, tablename, mode='append', properties=properties)
        return True

def psql_connection(p_config):
    """Connect to PostgreSQL server
    """
    db_host = p_config.get('reportdb', 'host')
    db_port = p_config.get('reportdb', 'port')
    db_name = p_config.get('reportdb', 'dbname')
    db_user = p_config.get('reportdb', 'dbuser')
    db_pass = p_config.get('reportdb', 'dbuserpass')
    psql_conn = psycopg2.connect(database=db_name, host=db_host, user=db_user,\
                                    password=db_pass, port=db_port)
    psql_cur = psql_conn.cursor()
    return psql_conn, psql_cur

def create_table(table, df_columns, psql_cur):
    """Create Table
    """

    query = "CREATE TABLE IF NOT EXISTS " + table + " ()"
    psql_cur.execute(query)
    psql_cur.connection.commit()

    for db_col in df_columns:
        query = "ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS " + db_col + " text;"
        psql_cur.execute(query)
        psql_cur.connection.commit()

def filter_df (unfiltered_df, spark_session):
    """Fileter rows
    """

    logging.info('**** Filtering Data ***')
    logging.info('**** Createing Temp View: patients  ****')
    unfiltered_df.createOrReplaceTempView('patients')

    sql_query = "select * from patients where \
                pt_address_state_prov in ('CA', 'OR', 'WA', 'ID', 'UT')"
    try:
        logging.info('**** Running Spark SQL: patients ****')
        filtered_df = spark_session.sql(sql_query)
    except AnalysisException as e_error:
        logging.error('Query Failed %s', e_error)
        sys.exit(-1)
    return filtered_df

def df_etl(sparksession, adtfeedname, segments, s3bucketprefix):
    """Apache Spark Magic happens here
    """

    if s3bucketprefix == 'JSON':
        logging.info('**** Get Redis JSONs ****')
        d_f = get_redis_jsons(redis_host, redis_port)
    else:
        logging.info('**** Get S3 JSONs ****')
        d_f = get_s3_jsons(sparksession, s3bucketprefix)

    d_f = lower_case_col_names(d_f)

    dict_batches = df_to_dict_batches(d_f)

    for dict_batch in dict_batches:
        # process HL7 segments
        d_f = process_data(dict_batch, segments, sparksession)
        if d_f:
            d_f = truncate_col_name(d_f)
            df_to_jdbc(d_f, adtfeedname)
            d_f = ''
        else:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',\
            handlers=[logging.StreamHandler(sys.stdout)])

    config = read_config('etl.config')
    spark_master = config.get('spark', 'master')
    spark_master_port = config.get('spark', 'masterport')
    aws_access_key = config.get('aws','access.key')
    aws_secret_key = config.get('aws','secret.key')
    redis_host = config.get('redis','host')
    redis_port = config.get('redis','port')

    IGNORE_SEG_FIELDS = ast.literal_eval(config.get('constants','IGNORE_SEG_FIELDS'))
    IGNORE_COMPONENT_FIELDS = ast.literal_eval(config.get('constants','IGNORE_COMPONENT_FIELDS'))
    HL7_SEGMENTS = ast.literal_eval(config.get('constants','HL7_SEGMENTS'))

    arg_parser = argparse.ArgumentParser(description='Process JSON to PostgreSQL')
    arg_parser.add_argument (
                             '--adt-feed-name',
                             dest='adt_feed_name',
                             action='store',
                             default='',
                             required=True,
                             help='Single value or comma separated, \
                                    Feed name i.e. adt_feed1 or adt_feed1,adt_feed2',
                            )
    arg_parser.add_argument (
                             '--s3-bucket-prefix',
                             dest='s3_bucket_prefix',
                             action='store',
                             default='JSON',
                             required=False,
                             help='Full path - <bucket-name>/prefix/',
                            )

    args = arg_parser.parse_args()

    # since I had to deal with several adt feeds, I chose to
    #  do it this way.
    adt_feed_name = args.adt_feed_name
    s3_bucket_full_path = args.s3_bucket_prefix


    spark = (SparkSession.builder
             .appName('adt_feed' + '_' + adt_feed_name + '_' + str(int(time.time())))
             .master(f'spark://{spark_master}:{spark_master_port}')
             .config('spark.executor.memory', '14g')
             .config('spark.driver.memory','14g')
             .config('spark.executor.cores', '4')
             .config('spark.task.cpus', '4')
             .config('spark.hadoop.fs.s3a.access.key', aws_access_key)
             .config('spark.hadoop.fs.s3a.secret.key', aws_secret_key)
             .config('spark.debug.maxToStringFields','200')
             .config('spark.jars',
                        '/var/tmp/sparkjars/postgresql-42.6.0.jar,\
                         /var/tmp/sparkjars/aws-java-sdk-bundle-1.12.262.jar,\
                         /var/tmp/sparkjars/hadoop-aws-3.3.4.jar')
             .getOrCreate())


    # can pass more than one name
    for adt_feed in adt_feed_name.split(','):
        logging.info('**** Starting for %s', adt_feed)
        df_etl(spark, adt_feed, HL7_SEGMENTS, s3_bucket_full_path)
        logging.info('**** Completed for %s', adt_feed)

    spark.stop()
