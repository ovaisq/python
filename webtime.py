#!/usr/bin/env python

"""
Calculate diagram load time in seconds by averaging times over 3
iterations
Wall clock time is capture at the beginning of page load and 
immediately after spinner changes from block to none
"""

import argparse
import csv
import json
import random
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException

def random_csv_file_name(some_text):
    epoch_str = str(pythonic_unix_time())
    rand_int_str = str(random.randint(2,99))
    csv_file_name = epoch_str + '_' + rand_int_str + '_' + some_text
    return csv_file_name + '.csv'

def pythonic_unix_time():
    return int(long((time.time() + 0.5) * 1000))

def avg_of_list(an_int_list):
    return sum(an_int_list) / float(len(an_int_list))

def run_it (driver, source, path):

    dom_settle_down_time_sec = 5
    dom_settle_down_time_ms = dom_settle_down_time_sec * 1000
    start_epoch_time = pythonic_unix_time()

    driver.get(source)

    # windows edge browser takes some time for dom to load
    # time.sleep(dom_settle_down_time_sec)

    # spinner starts out in block state
    spinner_style_attr_status = 'block'

    try:
        while 'block' in spinner_style_attr_status:
            element = driver.find_element_by_xpath(path)
            # javascript that gets a list of attributes
            attrs = driver.execute_script('var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;', element)
            att_json = json.loads(json.dumps(attrs))
            spinner_style_attr_status = att_json['style']
        # to help things settle down for canvas
        # this is subtracted from wall clock time totals
        time.sleep(dom_settle_down_time_sec) 
        my_start = driver.execute_script('return performance.timing.navigationStart;')
        my_end = driver.execute_script('return performance.timing.loadEventEnd;')
        print '  Page is ready!'
    except TimeoutException:
        print "Loading took too much time!"
        driver.quit()
    except WebDriverException:
        print "Something horribly went wrong with the WebDriver!"
        driver.quit()

    end_epoch_time = pythonic_unix_time()

    print '  Browser performance.timing render time', (my_end - my_start)
    print '  Wall clock render time                ', (end_epoch_time-dom_settle_down_time_ms) - start_epoch_time

    # return page render wall clock time
    return ((end_epoch_time-(dom_settle_down_time_ms)) - start_epoch_time)

def web_driver(browser_name, platform, version):
    '''
        Expects values Based on this tool:
        https://wiki.saucelabs.com/display/DOCS/Platform+Configurator#/
    '''
             
    desired_cap = {
        'browserName': browser_name
        ,'platform': platform
        ,'version': version
    }

    driver = webdriver.Remote(
    command_executor='http://'+username+':'+accessKey+'@ondemand.saucelabs.com:80/wd/hub',
    desired_capabilities=desired_cap)
    return driver

def csv_creator(outfile, header):
    with open(outfile,'wb') as csv_file:
        csv_writer = csv.DictWriter(csv_file, delimiter='\t', fieldnames=header)
        csv_writer.writeheader()
        return csv_writer
if __name__ == '__main__':

    #parse command line args
    arg_parser = argparse.ArgumentParser(prog='webtime.py', description='Diagram Load Time Benchmark Tool')

    arg_parser.add_argument(
                            '--browser-name'
                            , dest='browser_name'
                            , action='store'
                            , required=False
                            , default='Chrome'
                            , help='Chrome[default], visit: https://wiki.saucelabs.com/display/DOCS/Platform+Configurator#/'
                           )
    arg_parser.add_argument(
                            '--browser-platform'
                            , dest='platform'
                            , action='store'
                            , required=False
                            , default='Windows 10'
                            , help='Windows 10[default], see: https://wiki.saucelabs.com/display/DOCS/Platform+Configurator#/'
                           )
    arg_parser.add_argument(
                            '--browser-version'
                            , dest='version'
                            , action='store'
                            , required=False
                            , default='55'
                            , help='55[default], see: https://wiki.saucelabs.com/display/DOCS/Platform+Configurator#/'
                           )
    arg_parser.add_argument(
                            '--num-iterate'
                            , dest='num_iterate'
                            , action='store'
                            , required=False
                            , default=3
                            , help='Number of times to load a given diagram'
                           )
    arg_parser.add_argument(
                            '--urls'
                            , dest='urls'
                            , nargs='+'
                            , action='store'
                            , required=True
                            , default=None
                            , help='Single http://www.gliffy.com/ or a space separated\n'
                                    'list http://www.gliffy.com/ https://www.gliffy.com of Diagram urls'
                           )
    args = arg_parser.parse_args()

    urls = []

    # spinner xpath 
    x_path = '/html/body/div[1]/div/div[1]/div[1]'

    username = 'oquraishi';
    accessKey = 'ba01ebfc-8ae1-4e26-97ce-7c03d8ba9056';

    browser_name = args.browser_name
    platform = args.platform
    browser_version = args.version
    num_iterate = args.num_iterate
    urls = args.urls

    print 'Browser Name     :', browser_name
    print 'Browser Version  :', browser_version
    print 'Browser Platform :', platform
    print 'Num times to load:', num_iterate

    csv_file_name_text = ''.join([browser_name, '_', platform.replace(' ','_'), '_', browser_version]).lower()
    csv_file_name = random_csv_file_name(csv_file_name_text)
    header = ['diagram', browser_name + ' ' + browser_version]

    with open(csv_file_name,'wb') as csv_file:
        csv_writer = csv.DictWriter(csv_file, delimiter='\t', fieldnames=header)
        csv_writer.writeheader()

        for source in urls:
            print 'Source url       :', source
            print 'Results stored in:', csv_file_name
            driver = web_driver(browser_name, platform, browser_version)
            wall_clock_time_array = []

            for i in range(num_iterate):
                wall_clock_time = run_it(driver, source, x_path)
                wall_clock_time_array.append(wall_clock_time)

            driver.quit()

            csv_writer.writerow({
                                'diagram':source
                                , browser_name + ' ' + browser_version:avg_of_list(wall_clock_time_array)
                                }
                            )

            print 'Wall clock Render Avg in ms: %.2f' % avg_of_list(wall_clock_time_array)
    print 'Results stored in:', csv_file_name
