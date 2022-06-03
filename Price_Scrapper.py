#!/usr/bin/env python
# coding: utf-8

# In[1]: IMPORT LIB AND DEFINE FUNCTIONS
import requests
import pandas as pd
from bs4 import BeautifulSoup
import datetime
from time import sleep
import re
import os.path
from geopy.geocoders import Nominatim
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Import libraries for environment variables
import os
from dotenv import load_dotenv
load_dotenv()

#Wait for HTTP response
def r_wait(response, timeout, timewait):
    timer = 0
    if response.status_code <= 400:
        return response.status_code
    while response.status_code == 204:
        sleep(timewait)
        timer += timewait
        if timer > timeout:
            return 408
            break
        if response.status_code == 200:
            return response.status_code
            break

# function to get unique values 
def unique(list1): 

    # intilize a null list 
    unique_list = [] 

    # traverse for all elements 
    for x in list1: 
        # check if exists in unique_list or not 
        if x not in unique_list: 
            unique_list.append(x) 
            
    return unique_list

# return stem url
def stem_url(full_url):
    stem = full_url[0:full_url.find('com')+3]
    return stem

# open, read and quit chrome for url
def search_web(search_url):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    DRIVER_PATH = dir_path + '/chromedriver'
    service = Service(DRIVER_PATH)
    chrome_options = Options()  
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--kiosk")
    caps = DesiredCapabilities().CHROME
    caps["pageLoadStrategy"] = "normal"
    driver = webdriver.Chrome(desired_capabilities=caps, options=chrome_options, service=service)
    driver.get(search_url)
    
    sleep(3.0)
    
    scroll_pause_time = 3.0 # You can set your own pause time. My laptop is a bit slow so I use 1 sec
    screen_height = driver.execute_script("return window.screen.height;")   # get the screen height of the web
    i = 1
    while True:
        # scroll one screen height each time
        driver.execute_script("window.scrollTo(0, {screen_height}*{i});".format(screen_height=screen_height, i=i))  
        i += 1
        sleep(scroll_pause_time)
        # update scroll height each time after scrolled, as the scroll height can change after we scrolled the page
        scroll_height = driver.execute_script("return document.body.scrollHeight;")  
        # Break the loop when the height we need to scroll to is larger than the total scroll height
        if (screen_height) * i > scroll_height:
            break
    
    raw_html = driver.page_source
    driver.quit() 
    return raw_html

#Find and Clean Availability
def get_availability(text):
    if re.search('Full', text) is not None:
        availability = '0'
    if re.search('[0-9]+(?=/[0-9]+ Rooms)', text) is not None:
        availability = re.findall('[0-9]+(?=/[0-9]+ Rooms)', text)[0]
    return availability

#Find Pattern for Start or End Price and return
def get_price(x, pricetype):
    start_price_pattern = re.compile('(?<=From S\$)\d*,?\d{3}')
    start_price = ['']
    end_price = ['']
    if re.search(start_price_pattern, x) is not None and pricetype == 'start':
        start_price = re.findall(start_price_pattern, x)
        return start_price[0]
    end_price_pattern = re.compile('(?<=\-)\d*,?\d{3}')
    if re.search(end_price_pattern, x) is not None and pricetype == 'end':
        end_price = re.findall(end_price_pattern, x)
        return end_price[0]

#Find Pattern for Request Start or End Price and return
def get_r_price(x, pricetype):
    r_start_price_pattern = re.compile('<//>.{0,8}\d*,?\d{3}(?=/month|\-\d+)')
    r_start_price = ['']
    r_end_price = ['']
    if re.search(r_start_price_pattern, x) is not None and pricetype == 'start':
        r_start_price = re.findall(r_start_price_pattern, x)
        return r_start_price[0]
    r_end_price_pattern = re.compile('\-\d*,?\d{3}.{0,8}<//>')
    if re.search(r_end_price_pattern, x) is not None and pricetype == 'end':
        r_end_price = re.findall(r_end_price_pattern, x)
        return r_end_price[0]
    
#Get Geopoint from address   
def get_geopoint(app_name, address):
    sleep(2)
    geolocator = Nominatim(user_agent=app_name)
    location = geolocator.geocode(address, timeout=2)

    #Check for & before address
    if location == None and re.search('(?<=&\s).*', address):
        address = re.findall('(?<=&\s).*', address)[0]
        sleep(1.1)
        location = geolocator.geocode(address, timeout=1)


    #Check for ZIP and takeaway
    if location == None and re.search('\s*\w*\D*(?=[0-9]{4,6})', address):
        address = re.findall('\s*\w*\D*(?=[0-9]{4,6})', address)[0]
        sleep(1.1)
        location = geolocator.geocode(address, timeout=1)

    #Remove numbers
    if location == None and re.search('\d+', address):
        address = re.sub("\d+", "", address)
        sleep(1.1)
        location = geolocator.geocode(address, timeout=1)


    lat = location.latitude
    long = location.longitude

    return lat, long



# In[2]: SET VARIABLES

# Define Path where to save file
TO_SAVE_FILE_PATH = os.environ["TO_SAVE_FILE_PATH"]
URL = os.environ["URL"]
print(URL)



# In[3]: CLEAN AND GET DATA

# Get HTML and parse to BS4 and find all href tags
raw_html = search_web(URL)
print(raw_html)
soup = BeautifulSoup(raw_html, features='html.parser')

list_href = []
regex = re.compile('Unit.*')
separator_tag = '<//>'
for x in soup.find_all('a', {"class" : regex}, href=re.compile("/en/singapore")):
    x_text = x.get_text(separator=separator_tag, strip=True)
    x_href = separator_tag + 'https://hmlet.com' + x.get('href')
    x_full = x_text + x_href
    list_href.append(x_full)

#print(soup)

# Get list of unique URLs only
unique_href = unique(list_href)
list_result = []

#Clean data in every unique URL for ingestion
for x in unique_href:
    
    price_pattern = re.compile('S\$.*\-.*/month')
    if re.search(price_pattern, x) is not None:    
        #Find and Clean Start and End Price per month
        start_price = separator_tag + get_price(x, 'start') + separator_tag
        end_price = get_price(x, 'end') + separator_tag
        t_start_price = get_r_price(x, 'start')
        t_end_price = get_r_price(x, 'end')
        x = x.replace(t_start_price, start_price)
        x = x.replace(t_end_price, end_price)
        split_x = x.split(separator_tag)
        split_x.insert(0, datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())
        availability = get_availability(x)
        split_x.insert(-1, availability)
        lat, long = get_geopoint('geo_finds', split_x[4])
        split_x.append(lat)
        split_x.append(long)
        list_result.append(split_x)

    price_pattern2 = re.compile('(?<=From S\$)[0-9]{0,2},?[0-9]{3}/month<//>')
    if re.search(price_pattern2, x) is not None:
        #Find and Clean Start Price per month ONLY
        start_price = separator_tag + get_price(x, 'start') + separator_tag
        end_price = '0'
        t_start_price = get_r_price(x, 'start')
        t_end_price = '/month'
        x = x.replace(t_start_price, start_price)
        x = x.replace(t_end_price, end_price)
        split_x = x.split(separator_tag)
        split_x.insert(0, datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())
        availability = get_availability(x)
        split_x.insert(-1, availability)
        lat, long = get_geopoint('geo_finds', split_x[4])
        split_x.append(lat)
        split_x.append(long)
        list_result.append(split_x)
        
print('all rows:',len(list_href),', unique rows:', len(unique_href), ', rows with price range:', len(list_result))
print(list_result)



# In[4]: EXPORT

# Define field names and types, add data to df for export
column_names = ['DateTime', 'Availability', 'Region', 'Property','Address','Start Price', 'End Price', 'Available Slots', 'Url', 'Lat', 'Lon']

df = pd.DataFrame(list_result, columns=column_names)

df['Start Price'] = df['Start Price'].str.replace(',', '').astype(float)
df['End Price'] = df['End Price'].str.replace(',', '').astype(float)
df['Lat'] = df['Lat'].astype(float)
df['Lon'] = df['Lon'].astype(float)

df = df.sort_values(by='Start Price')
df = df.replace(to_replace=0, value='')

print(df)

# Export df to csv file
if os.path.isfile(TO_SAVE_FILE_PATH):
    print ("File exist")
    df.to_csv(TO_SAVE_FILE_PATH, mode='a', header=False, index=False)
else:
    print ("File not exist")
    df.to_csv(TO_SAVE_FILE_PATH, mode='w', header=True, index=False)






