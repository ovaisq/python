#!/usr/bin/env python3
"""Get AWS costs, store em in postgresql database

	https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ce/client/get_cost_and_usage.html
"""

import boto3
import configparser
import datetime
import json
import logging
import pathlib
import psycopg2
import time

def aws_account_id():
    """get aws account number
    """
    
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    return account_id

def read_config(file_path):
    """ read config file
    """
    
    if pathlib.Path(file_path).exists():
        config_obj = configparser.RawConfigParser()
        config_obj.read(file_path)
        return config_obj
    else:
        raise FileNotFoundError(f"Config file {file_path} not found.")

def psql_connection(p_config):
    """Connect to PostgreSQL server
    """

    db_config = {
        'database': p_config.get('psqldb', 'dbname'),
        'host': p_config.get('psqldb', 'host'),
        'user': p_config.get('psqldb', 'dbuser'),
        'password': p_config.get('psqldb', 'dbuserpass'),
        'port': p_config.get('psqldb', 'port'),
    }

    try:
        psql_conn = psycopg2.connect(**db_config)
        psql_cur = psql_conn.cursor()
        return psql_conn, psql_cur
    except psycopg2.Error as e:
        logging.error(f"Error connecting to PostgreSQL: {e}")
        raise

def db_write(table_name, dataobject, psql_cursor):
    """Write to db table
    """
    
    cols = str(tuple(dataobject.keys())).replace("'","")
    vals = str(tuple(dataobject.values()))
    query = f"INSERT INTO {table_name} {cols} VALUES {vals};"
    try:
        psql_cursor.execute(query)
        psql_cursor.connection.commit()
    except psycopg2.Error as e:
        logging.error(f"Unable to execute query or commit for table {table_name} - {e}")
        raise

if __name__ == "__main__":
    
    logging.basicConfig(level=logging.INFO)
    EXCLUDED_KEY = {'Tax'}
    start_date = datetime.date(2023,9,1) #TODO: parameterize it
    end_date = start_date + datetime.timedelta(days=30) #TODO: parameterize it
    timestamp = int(time.time())
    account_id = aws_account_id()

    boto_client = boto3.client('ce') #aws cost explorer
    time_period = {
                    'Start' : str(start_date),
                    'End' : str(end_date) #exclusive
                  }
    granularity = 'DAILY'
    metrics = ['AmortizedCost','BlendedCost','UnblendedCost']
    group_by = [
                {
                 'Type': 'DIMENSION',
                 'Key' : 'SERVICE'
                },
                {
                 'Type': 'DIMENSION',
                 'Key': 'USAGE_TYPE'
                }
               ] 

    p_config = read_config('setup.config')
    table_name = p_config.get('psqldb', 'tablename')

    response = json.loads(json.dumps(boto_client.get_cost_and_usage(TimePeriod=time_period, Granularity=granularity, Metrics=metrics, GroupBy=group_by)))

    _, psql_cur = psql_connection(p_config)
    
    for groups_key in response['ResultsByTime']:
        for aws_service_key_name in groups_key['Groups']:
            if aws_service_key_name['Keys'][0] not in EXCLUDED_KEY:
                time_period = groups_key['TimePeriod']['Start']
                aws_service = aws_service_key_name['Keys'][0]
                usage_type = aws_service_key_name['Keys'][1]
                for cost_type in metrics:
                    amount_usd = aws_service_key_name['Metrics'][cost_type]['Amount']
                    db_object = {
                                 'timestamp' : timestamp,
                                 'account_id' : account_id,
                                 'time_period' : time_period,
                                 'aws_service' : aws_service,
                                 'cost_type' : cost_type,
                                 'usage_type' : usage_type,
                                 'amount' : amount_usd
                                }
                    db_write(table_name, db_object, psql_cur)