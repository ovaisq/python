#!/usr/bin/env python3
"""Reddit Data Scrapper Service
    Collects submissions, comments for each submission, author of each submission,
    author of each comment to each submission, and all comments for each author.
    Also, subscribes to subreddit that a submission was posted to

    Uses Gunicorn WSGI

    Install Python Modules:
        > pip3 install -r requirements.txt

    Get Reddit API key: https://www.reddit.com/wiki/api/

    Gen SSL key/cert
        > openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 3650

    Create Database and tables:
        reddit.sql

    Generate Flask App Secret Key:
        >  python -c 'import secrets; print(secrets.token_hex())'

    Update setup.config with pertinent information (see setup.config.template)

    Run Service:
    (see https://docs.gunicorn.org/en/stable/settings.html for config details)

        > gunicorn --certfile=cert.pem \
                   --keyfile=key.pem \
                   --bind 0.0.0.0:5000 \
                   reddit_gunicorn:app \
                   --timeout 2592000 \
                   --threads 4 \
                   --reload

    Customize it to your hearts content!

    LICENSE: The 3-Clause BSD License - license.txt

    TODO:
        - Add Swagger Docs
        - Add long running task queue
            - Queue: task_id, task_status, end_point
            - Kafka
        - Revisit Endpoint logic add robust error handling
        - Add scheduler app - to schedule some of these events
            - scheduler checks whether or not a similar tasks exists
        - Add logic to handle list of lists with NUM_ELEMENTS_CHUNK elementsimport configparser
"""

import asyncio
import configparser
import hashlib
import json
import logging
import ollama
import pathlib
import random
import string
import time
from random import randrange

import psycopg2
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from praw import Reddit
from prawcore import exceptions
from ollama import AsyncClient
from ollama import Client

app = Flask('Reddit Scraper')

# constants
NUM_ELEMENTS_CHUNK = 25
CONFIG_FILE = 'setup.config'
CONFIG = configparser.RawConfigParser()
CONFIG.read(CONFIG_FILE)
LLMS = CONFIG.get('service','LLMS').split(',')
IGNORE_SUBS = ['u_zackmedude']

# Flask app config
app.config.update(
                  JWT_SECRET_KEY= CONFIG.get('service', 'JWT_SECRET_KEY'),
                  SECRET_KEY=CONFIG.get('service', 'APP_SECRET_KEY'),
                  PERMANENT_SESSION_LIFETIME=172800 #2 days
                 )
jwt = JWTManager(app)

# Reddit authentication
REDDIT = Reddit(
                client_id=CONFIG.get('reddit', 'client_id'),
                client_secret=CONFIG.get('reddit', 'client_secret'),
                password=CONFIG.get('reddit', 'password'),
                user_agent=CONFIG.get('reddit', 'user_agent'),
                username=CONFIG.get('reddit', 'username'),
               )

def unix_ts_str():
    """Unix time as a string
    """

    dt = str(int(time.time())) # unix time
    return dt

def gen_internal_id():
    """Generate 10 number internal document id
        this id is used to track edited version of original document
    """

    # reddit uses 7 character long alphanum ids - to avoid any confusion
    #  using a 10 char long alphanum id to tag edited/modified analysis responses
    ten_alpha_nums = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    #return ten_alpha_nums
    pass #TBD

def list_into_chunks(a_list, num_elements_chunk):
    """Split list into list of lists with each list containing
        num_elements_chunk elements

        Returns a list of list or if list contains equal or less
         elements, then just that list
    """

    if len(a_list) > num_elements_chunk:
        for i in range(0, len(a_list), num_elements_chunk):
            yield a_list[i:i + num_elements_chunk]
    else:
        yield a_list

def read_config(file_path):
    """Read setup config file
    """

    if pathlib.Path(file_path).exists():
        config_obj = configparser.RawConfigParser()
        config_obj.read(file_path)
        return config_obj
    raise FileNotFoundError(f"Config file {file_path} not found.")

def psql_connection():
    """Connect to PostgreSQL server
    """

    db_config = read_config(CONFIG_FILE)['psqldb']
    try:
        psql_conn = psycopg2.connect(**db_config)
        psql_cur = psql_conn.cursor()
        return psql_conn, psql_cur
    except psycopg2.Error as e:
        logging.error(f"Error connecting to PostgreSQL: {e}")
        raise

def get_select_query_results(sql_query):
    """Execute a query, return all rows for the query
    """

    conn, cur = psql_connection()
    try:
        cur.execute(sql_query)
        result = cur.fetchall()
        conn.close()
        return result
    except psycopg2.Error as e:
        logging.error(f"{e}")
        raise

def insert_data_into_table(table_name, data):
    """Insert data into table
    """

    conn, cur = psql_connection()
    try:
        placeholders = ', '.join(['%s'] * len(data))
        columns = ', '.join(data.keys())
        sql_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) \
                     ON CONFLICT DO NOTHING;"
        cur.execute(sql_query, list(data.values()))
        conn.commit()
    except psycopg2.Error as e:
        logging.error(f"{e}")
        raise

def get_new_data_ids(table_name, unique_column, reddit_data):
    """Get object ids for new messages on reddit
        query db for existing ids
        query api for all ids
        return the diff from the api
    """

    query = f"SELECT {unique_column} FROM {table_name} GROUP BY {unique_column};"

    data_ids_db = [] # array to hold ids from database table
    data_ids_reddit = [] # arrary to hold ids from reddit api call

    result = get_select_query_results(query)
    for row in result:
        data_ids_db.append(row[0])

    for item in reddit_data:
        data_ids_reddit.append(item.id)

    new_list = set(data_ids_reddit) - set(data_ids_db)
    #TODO new_list_of_lists = list(list_into_chunks(list(newlist), NUM_ELEMENTS_CHUNK))
    return list(new_list) 

def db_get_authors():
    """Get list of authors from db table
        return python list
    """

    author_list = []
    query = """SELECT author_name FROM author GROUP BY author_name;"""
    authors = get_select_query_results(query)
    for row in authors:
        author_list.append(row[0])
    return author_list

def sleep_to_avoid_429(counter):
    """Sleep for a random number of seconds to avoid 429
        TODO: handle status code from the API
        but it's better not to trigger the 429 at all...
    """

    counter += 1
    if counter > 23: # anecdotal magic number
        sleep_for = randrange(65, 345)
        logging.info(f"Sleeping for {sleep_for} seconds")
        time.sleep(sleep_for)
        counter = 0
    return counter

@app.route('/analyze_post', methods=['GET'])
@jwt_required()
def analyze_post_endpoint():
    """Chat prompt a given post_id
    """

    post_id = request.args.get('post_id')
    analyze_this(post_id)
    return jsonify({'message': 'analyze_post endpoint'})

@app.route('/analyze_posts', methods=['GET'])
@jwt_required()
def analyze_posts_endpoint():
    """Chat prompt all post_ids
    """

    analyze_posts()
    return jsonify({'message': 'analyze_posts endpoint'})

def db_get_post_ids():
    """List of post_ids, filtering out pre-analyzed post_ids from this
    """

    post_id_list = []
    sql_query = """SELECT post_id 
                   FROM post
                   WHERE post_body NOT IN ('', '[removed]', '[deleted]')
                   AND post_id NOT IN (SELECT analysis_document ->> 'post_id' AS pid 
                                       FROM analysis_documents
                                       GROUP BY pid);"""
    post_ids = get_select_query_results(sql_query)
    if not post_ids:
        logging.warning(f"db_get_post_ids(): no post_ids found in DB")
        return

    for a_post_id in post_ids:
        post_id_list.append(a_post_id[0])

    return post_id_list

def analyze_posts():
    """
    """

    post_ids = db_get_post_ids()

    counter = 0
    for a_post_id in post_ids:

        asyncio.run(analyze_this(a_post_id))
        counter = sleep_to_avoid_429(counter)

async def analyze_this(post_id):
    """Analyze text
    """
    logging.info(f"Analyzing post ID {post_id}")
    dt = unix_ts_str()
    client = AsyncClient(host=CONFIG.get('service','OLLAMA_API_URL'))

    sql_query = f"""SELECT post_title, post_body, post_id
                    FROM post
                    WHERE post_id='{post_id}'
                    AND post_body NOT IN ('', '[removed]', '[deleted]');"""
    post_data =  get_select_query_results(sql_query)
    if not post_data:
        logging.warning(f"Post ID {post_id} contains no body")
        return

    # post_title, post_body for ChatGPT
    text = post_data[0][0] + post_data[0][1]
    # post_id
    post_id = post_data[0][2]

    for llm in LLMS:
        response = await client.chat(
                               model=llm,
                               stream=False,
                               messages=[
                                         {
                                          'role': 'user',
                                          'content': text
                                         },
                                        ],
                               options = {
                                          'temperature' : 0
                                         }
                              )

        # chatgpt analysis
        analysis = response['message']['content']

        # this is for the analysis text only - the idea is to avoid
        #  duplicate text document, to allow indexing the column so
        #  to speed up search/lookups
        analysis_sha512 = hashlib.sha512(str.encode(analysis)).hexdigest()

        # jsonb document
        analysis_document = {
                             'unix_time' : dt,
                             'post_id' : post_id,
                             'llm' : llm,
                             'analysis' : analysis
                            }
        analysis_data = {
                         'shasum_512' : analysis_sha512,
                         'analysis_document' : json.dumps(analysis_document)
                        }

        insert_data_into_table('analysis_documents', analysis_data)
        response = {}
        analysis_document = {}
        ayalysis_data = {}

@app.route('/login', methods=['POST'])
def login():
    """Generate JWT
    """

    secret = request.json.get('api_key')

    if secret != CONFIG.get('service','SRVC_SHARED_SECRET'):  # if the secret matches
        return jsonify({"message": "Invalid secret"}), 401

    # generate access token
    access_token = create_access_token(identity=CONFIG.get('service','IDENTITY'))
    return jsonify(access_token=access_token), 200

@app.route('/get_sub_post', methods=['GET'])
@jwt_required()
def get_post_endpoint():
    """Get submission post content for a given post id
    """

    post_id = request.args.get('post_id')
    get_sub_post(post_id)
    return jsonify({'message': 'get_sub_post endpoint'})

@app.route('/get_sub_posts', methods=['GET'])
@jwt_required()
def get_sub_posts_endpoint():
    """Get submission posts for a given subreddit
    """

    sub = request.args.get('sub')
    get_sub_posts(sub)
    return jsonify({'message': 'get_sub_posts endpoint'})

def get_sub_post(post_id):
    """Get a submission post
    """

    logging.info(f"Getting post id {post_id}")

    post = REDDIT.submission(post_id)
    post_data = get_post_details(post)
    insert_data_into_table('post', post_data)
    get_post_comments(post)

def get_sub_posts(sub):
    """Get all posts for a given sub
    """

    logging.info(f"Getting posts in subreddit {sub}")
    try:
        posts = REDDIT.subreddit(sub).hot(limit=None)
        new_post_ids = get_new_data_ids('post', 'post_id', posts)
        counter = 0
        for post_id in new_post_ids:
            get_sub_post(post_id)
            counter = sleep_to_avoid_429(counter)
    except AttributeError as e:
        # store this for later inspection
        error_data = {
                      'item_id': sub,
                      'item_type': 'GET SUB POSTS',
                      'error': e.args[0]
                     }
        insert_data_into_table('errors', error_data)
        logging.warning(f"GET SUB POSTS {sub} {e.args[0]}")

def get_post_comments(post_obj):
    """Get all comments made to a submission post
    """

    logging.info(f"Getting comments for post {post_obj.id}")

    for comment in post_obj.comments:
        comment_data = get_comment_details(comment)
        insert_data_into_table('comment', comment_data)

def get_post_details(post):
    """Get details for a submission post
    """

    post_author = post.author.name if post.author else None

    if post_author:
        process_author(post_author)

    post_data = {
                 'subreddit': post.subreddit.display_name,
                 'post_id': post.id,
                 'post_author': post_author,
                 'post_title': post.title,
                 'post_body': post.selftext,
                 'post_created_utc': int(post.created_utc),
                 'is_post_oc': post.is_original_content,
                 'is_post_video': post.is_video,
                 'post_upvote_count': post.ups,
                 'post_downvote_count': post.downs,
                 'subreddit_members': post.subreddit_subscribers
                }
    return post_data

def get_comment_details(comment):
    """Get comment details
    """

    comment_author = comment.author.name if comment.author else None
    comment_submitter = comment.is_submitter if hasattr(comment, 'is_submitter') else None
    comment_edited = str(int(comment.edited)) if comment.edited else False

    if comment_author:
        process_author(comment_author)

    comment_data = {
                    'comment_id': comment.id,
                    'comment_author': comment_author,
                    'is_comment_submitter': comment_submitter,
                    'is_comment_edited': comment_edited,
                    'comment_created_utc': int(comment.created_utc),
                    'comment_body': comment.body,
                    'post_id': comment.submission.id,
                    'subreddit': comment.subreddit.display_name
                   }
    return comment_data

@app.route('/get_author_comments', methods=['GET'])
@jwt_required()
def get_author_comments_endpoint():
    """Get all comments for a given author
    """

    author = request.args.get('author')
    get_author_comments(author)
    return jsonify({'message': 'get_author_comments endpoint'})

@app.route('/get_authors_comments', methods=['GET'])
@jwt_required()
def get_authors_comments_endpoint():
    """Get all comments for each author from a list of author in db
    """

    get_authors_comments()
    return jsonify({'message': 'get_authors_comments endpoint'})

def process_author(author_name):
    """Process author information.
    """

    logging.info(f"Processing Author {author_name}")

    author_data = {}
    try:
        author = REDDIT.redditor(author_name)
        if author.name != 'AutoModerator':
            author_data = {
                           'author_id': author.id,
                           'author_name': author.name,
                           'author_created_utc': int(author.created_utc),
                          }
            insert_data_into_table('author', author_data)
    except (AttributeError, TypeError, exceptions.NotFound) as e:
        # store this for later inspection
        error_data = {
                      'item_id': author_name,
                      'item_type': 'AUTHOR',
                      'error': e.args[0]
                     }
        insert_data_into_table('errors', error_data)
        logging.warning(f"AUTHOR {author_name} {e.args[0]}")

def get_author(anauthor):
    """Get author info of a comment or a submission
    """

    process_author(anauthor)
    get_author_comments(anauthor)

def process_comment(comment):
    """Process a single comment
    """

    comment_body = comment.body

    if comment_body not in ('[removed]', '[deleted]') and comment.author.name != 'AutoModerator':
        comment_data = get_comment_details(comment)
        insert_data_into_table('comment', comment_data)
        orig_post = REDDIT.submission(comment_data['post_id'])
        post_data = get_post_details(orig_post)
        insert_data_into_table('post', post_data)

    if comment_body in ('[removed]', '[deleted]'): #removed or deleted comments
        comment_data = get_comment_details(comment)
        insert_data_into_table('comment', comment_data)

def get_authors_comments():
    """Get comments and posts for authors listed in the author table, 
        insert data into db
    """

    authors = db_get_authors()
    if not authors:
        logging.warning(f"db_get_authors(): No authors found in DB")
        return

    for an_author in authors:
        try:
            redditor = REDDIT.redditor(an_author)
            redditor.fullname
            get_author_comments(an_author)
        except exceptions.NotFound as e:
            # store this for later inspection
            error_data = {
                          'item_id': an_author,
                          'item_type': 'REDDITOR DELETED',
                          'error': e.args[0]
                         }
            insert_data_into_table('errors', error_data)
            logging.warning(f"AUTHOR DELETED {an_author} {e.args[0]}")


def get_author_comments(author):
    """Get author comments, author posts, insert data into db
    """

    logging.info(f"Getting comments for {author}")

    try:
        redditor = REDDIT.redditor(author)
        comments = redditor.comments.hot(limit=None)
        author_comments = get_new_data_ids('comment', 'comment_id', comments)
        if not author_comments:
            logging.info(f"{author} has no new comments")
            return

        counter = 0
        if author_comments:
            num_comments = len(author_comments)
            logging.info(f"{author} {num_comments} new comments")
            for comment_id in author_comments:
                comment = REDDIT.comment(comment_id)
                process_comment(comment)
                counter = sleep_to_avoid_429(counter)

    except AttributeError as e:
        # store this for later inspection
        error_data = {
                      'item_id': comment_id,
                      'item_type': 'COMMENT',
                      'error': e.args[0]
                     }
        insert_data_into_table('errors', error_data)
        logging.warning(f"AUTHOR COMMENT {comment_id} {e.args[0]}")

@app.route('/join_new_subs', methods=['GET'])
@jwt_required()
def join_new_subs_endpoint():
    """Join all new subs from post database
    """

    join_new_subs()
    return jsonify({'message': 'join_new_subs_endpoint endpoint'})

def join_new_subs():

    logging.info('Joining New Subs')
    new_subs = []
    dt = unix_ts_str()

    # get new subs
    sql_query = """select subreddit from post where subreddit not in \
                (select subreddit from subscription) group by subreddit;"""
    new_sub_rows = get_select_query_results(sql_query)
    if not author_comments:
        logging.info('No new subreddits to join')
        return

    for a_row in new_sub_rows:
        if a_row[0] not in IGNORE_SUBS:
            new_subs.append(a_row[0])

    if new_subs:
        for new_sub in new_subs:
            logging.info(f'Joining new sub {new_sub}')
            try:
                REDDIT.subreddit(new_sub).subscribe()
                sub_data = {
                            'datetimesubscribed' : dt,
                            'subreddit' : new_sub
                        }
                insert_data_into_table('subscription', sub_data)
            except (exceptions.Forbidden, exceptions.NotFound) as e:
                # store this for later inspection
                error_data = {
                              'item_id': new_sub,
                              'item_type': 'SUBREDDIT',
                              'error': e.args[0]
                             }
                insert_data_into_table('errors', error_data)
                logging.error(f'Unable to join {new_sub} - {e.args[0]}')

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO) # init logging

    # non-production WSGI settings:
    #  port 5000, listen to local ip address, use ssl
    # in production we use gunicorn
    app.run(port=5000,
            host='0.0.0.0',
            ssl_context=('cert.pem', 'key.pem'),
            debug=True)
