# utils.py

import time
import random
import string

def unix_ts_str():
    """Unix time as a string"""
    dt = str(int(time.time())) # unix time
    return dt

def gen_internal_id():
    """Generate 10 number internal document id"""
    ten_alpha_nums = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return ten_alpha_nums

def list_into_chunks(a_list, num_elements_chunk):
    """Split list into list of lists with each list containing
        num_elements_chunk elements"""
    if len(a_list) > num_elements_chunk:
        for i in range(0, len(a_list), num_elements_chunk):
            yield a_list[i:i + num_elements_chunk]
    else:
        yield a_list

def sleep_to_avoid_429(counter):
    """Sleep for a random number of seconds to avoid 429
        TODO: handle status code from the API
        but it's better not to trigger the 429 at all...
    """

    counter += 1
    if counter > 23: # anecdotal magic number
        sleep_for = random.randrange(65, 345)
        logging.info(f"Sleeping for {sleep_for} seconds")
        time.sleep(sleep_for)
        counter = 0
    return counter
