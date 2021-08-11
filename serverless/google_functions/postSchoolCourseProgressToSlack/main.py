#!/usr/bin/env python3

import ast
import config
import coursesequence
import json
import os
import sqlite3
import sys
import requests

from google.cloud import bigquery
from google.cloud import logging
from string import Template

def total_days_left(curr_sequence_num):
    """Total days left"""

    days = []
    courses_info_dict = coursesequence.course_sequence
    for i in range(curr_sequence_num,num_total_course()):
        days.append(courses_info_dict[i]['days'])
    return sum(days)

def fix_course_name(course_name):
    """Fix course name variance
    Args:
        course_name: name of the course (string)
    Returns:
        corrected course name (string)
    """

    if course_name == 'Why Multiply before Adding':
        return 'Why multiply before adding'
    elif course_name == 'Important Academic Words in Math':
        return 'Important academic words in math'
    else:
        return course_name

def num_total_course():
    """Get total number of courses
    Args:
        None
    Returns:
        Total numbers of courses (int)
    """

    return len(coursesequence.course_sequence.keys())

def num_courses_left(curr_sequence_num):
    """Number of courses remaining
    Args:
        curr_sequence_num: course sequence number (int)
    Returns:
        Number of courses remaining (int)
    """

    return num_total_course() - curr_sequence_num

def get_course_name(sequence_num, logger):
    """Get Course Name by sequenece num
    Args:
        sequence_num: sequence number of a given course (int)
    Returns:
        course name (string)
    """

    courses_info_dict = coursesequence.course_sequence
    try:
        course_name = courses_info_dict[sequence_num]['name']
        return course_name
    except Exception as error:
        log_message = Template('Course name not found for sequence num ' + sequence_num + ' '
                       '$message.')
        logger.log_text(log_message.safe_substitute(message=error), severity='ERROR')
        sys.exit(-1)

def get_course_seq_num(course_name, logger):
    """Get Course Name sequence num
    Args:
        course_name: course name (string)
    Returns:
        For a valid course name:
            course sequence number (int)
        For a non-existent course name:
            exit script
    """

    courses_info_dict = coursesequence.course_sequence
    try:
        #search for a value for a given key
        sequence_num = next((key for key, val in courses_info_dict.items() if val['name'] == course_name), None)
        if sequence_num != None:
            return sequence_num
        else:
            log_message = Template('Course name ' + course_name + ' not found'
                           '$message.')
            logger.log_text(log_message.safe_substitute(message=error), severity='ERROR')
            sys.exit(-1)

    except Exception as error:
        log_message = Template('Course name ' + course_name + ' not found'
                       '$message.')
        logger.log_text(log_message.safe_substitute(message=error), severity='ERROR')
        sys.exit(-1)

def next_course_info(course_name, logger):
    """Get Next Course info"""
    next_course_sequence_num = get_course_seq_num(course_name, logger) + 1
    next_course_name = get_course_name(next_course_sequence_num, logger)
    course_info_json = {
                        'seq_num' : next_course_sequence_num,
                        'name' : next_course_name,
                        'num_courses_left' : num_courses_left(get_course_seq_num(course_name, logger)),
                        'num_days_left' : total_days_left(get_course_seq_num(course_name, logger))
                       }
    return course_info_json


def file_to_string(sql_path):
    """Converts a SQL file holding a SQL query to a string.
    Args:
        sql_path: String containing a file path
    Returns:
        String representation of a file's contents
    """

    project_id = os.environ['GCP_PROJECT']
    with open(sql_path, 'r') as sql_file:
        return sql_file.read().replace('%%PROJECT-ID%%', project_id)


def execute_query(bq_client, logger):
    """Executes transformation query to a new destination table.
    Args:
        bq_client: Object representing a reference to a BigQuery Client
    """

    sql = file_to_string(config.config_vars['sql_file_path'])
    logger.log_text('Attempting school_lessons query...', severity='INFO')
    # Execute Query
    query_job = bq_client.query(sql)
    return query_job  # Waits for the query to finish

def sqlite_cursor():
    """Creates an in-memory instance of SQLite3 DB
    Args:
        None
    Returns:
        DB Cursor Object
    """

    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    return cursor

def sqlite_create_table():
    """Creates an in-memory table
    Args:
        None
    Returns:
        DB Cursor Object, for data CRUD operations on the table
    """

    cur = sqlite_cursor()
    cur.execute('''CREATE TABLE results (id integer primary key, org text, course text, next_course text, courses_left integer, num_days_left integer)''')
    return cur

def post_to_slack(payload, logger):
    """Posts payload to Slack Channel
    Args:
        payload
            "{
              \"username\":\"CloudFunction\",
              \"text\": \"[ ORG ] has progressed to the following course: Power Stance\\n
             "}"
    Returns:
        True - if post to slack was a success
        False - if post to slack failed
    """
    
    headers = {
               'Content-Type': 'application/json'
              }
    slack_url = config.config_vars['slack_url']
    response = requests.request("POST", slack_url, headers=headers, data=payload)
    if response.status_code == 200:
        logger.log_text('Successfully posted to the Slack Channel', severity='INFO')
        return True
    else:
        logger.log_text(response.text, severity='ERROR')
        return False

def main(data, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
        data (dict): Event payload.
        context (google.cloud.functions.Context): Metadata for the event.
    """
    
    #google cloud logging
    logging_client = logging.Client()
    log_name = 'postSchoolCourseProgressToSlack'
    logger = logging_client.logger(log_name)

    #bigQ
    bq_client = bigquery.Client()
    try:
        query_job = execute_query(bq_client, logger)
        logger.log_text('Completed school_lessons query...', severity='INFO')
    except Exception as error:
        log_message = Template('Query failed due to '
                               '$message.')
        logger.log_text(log_message.safe_substitute(message=error), severity='ERROR')
        sys.exit(-1)

    #convert string to list of dictionaries
    records = [dict(row) for row in query_job]
    json_obj = json.dumps(str(records))
    dicts = ast.literal_eval(json_obj.replace('\\','').strip('"'))

    #org and course exclude list
    school_exclude_list = config.config_vars['school_exclude_list']
    course_exclude_list = config.config_vars['course_exclude_list']

    #store subset of columns in SQLite3 in-memory db
    acur = sqlite_create_table()
    for i in dicts:
        if i['school_name'] not in school_exclude_list:
            course_name = fix_course_name(i['course'])
            #skip if course is part of the exclude list
            if course_name in course_exclude_list:
                continue
            next_course = next_course_info(course_name, logger)['name']
            num_courses_left = next_course_info(course_name, logger)['num_courses_left']
            num_days_left = next_course_info(course_name, logger)['num_days_left']
            acur.execute("INSERT INTO results(org,course,next_course,courses_left,num_days_left) values (?, ?, ?, ?, ?)", 
                        (i['school_name'], course_name, next_course, num_courses_left, num_days_left))

    if os.environ['GCP_PROJECT'] == '<gcp project name>':
        this_env = 'Production'
    else:
        this_env = os.environ['GCP_PROJECT']

    #sort and group course per org table, add to payload
    payload_text = '[Environment: ' + this_env + ']\n'
    for row in acur.execute ("select org, course, next_course, courses_left, num_days_left from results where id in (select max(id) from results group by org)").fetchall():
        payload_text += '\t['+row[0]+']\n'
        payload_text += '\t\tCurrent course  : '+row[1]+'\n'
        payload_text += '\t\tNext Course     : '+row[2]+'\n'
        payload_text += '\t\tNum courses left: '+str(row[3])+'\n'
        payload_text += '\t\tNum days left   : '+str(row[4])+'\n'

    payload = "{\"name\" : \"CourseProgressPerOrganization\",\"text\" :"
    payload += "\""
    payload +=  payload_text
    payload += "\"}"

    #slack it
    post_to_slack(payload, logger)

if __name__ == '__main__':
    main('data', 'context')
