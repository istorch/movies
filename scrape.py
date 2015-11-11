# Script for scraping movie data from themoviedb and omdbapi
# by Isaac Storch
# 10/2015

import requests as rq
import pandas as pd
import re
import numpy as np
import time
from sqlalchemy import create_engine
import pprint
import sys

# some global variables
themoviedbCols = ['budget', 'genres', 'id', 'imdb_id', 'production_companies', 'release_date',
                  'revenue', 'runtime', 'vote_average', 'vote_count']
omdbapiCols = ['Metascore', 'imdbRating', 'imdbVotes', 'tomatoFresh', 'tomatoRotten',
        'tomatoMeter', 'tomatoRating', 'tomatoUserMeter', 'tomatoUserRating', 'tomatoUserReviews',
        'BoxOffice', 'Actors', 'Director', 'Genre', 'Production', 'Writer']
apikey = '2f34813bfafc074009a48bb1b7b8373b'
        
# query themoviedb for a list of ids for the most grossing movies
def get_movie_ids(page, session):
    ids = []
    # get themoviedb id
    resp = session.get('https://api.themoviedb.org/3/discover/movie?sort_by=revenue.desc&page=%d&api_key=%s' % (page, apikey))
    # print 'Retrieved data from: ' + resp.url
    json = resp.json()
    
    for result in json['results']:
        if result.has_key('id'):
            ids.append(result['id'])
        else: print 'No id key found'
    
    return ids

# get movie info from themoviedb (seems to have more complete data)
def get_movie_info(id, session):
    resp = session.get('https://api.themoviedb.org/3/movie/%s?api_key=%s' % (id, apikey))
    # print 'Retrieved data from: ' + resp.url
    
    json = resp.json()
    strlist = []
    if json.has_key('status_code'):
        print 'Error from server: %s' % json['status_message']
        s = pd.Series()
    else:
        # print ('Processing data for: %s' % json['title']).encode(sys.stdout.encoding, errors='replace')
        for key in themoviedbCols:
            if key == 'genres' or key == 'production_companies':    # combine strings together with commas
                temp = json[key]
                data = ', '.join([dict['name'] for dict in temp])
            else: data = str(json[key])
            strlist.append(data)
        s = pd.Series(strlist, index = themoviedbCols, name = json['title'])
        
    return s
    
# get score data from omdbapi (has rotten tomatoes, etc)
def get_movie_scores(imdbid, session):
    # query the api
    resp = session.get('http://www.omdbapi.com/?i=%s&tomatoes=true' % imdbid)
    print 'Retrieved data from: ' + resp.url
    
    json = resp.json()
    strlist = []
    print ('Movie title: %s' % json['Title']).encode(sys.stdout.encoding, errors='replace')
    for key in omdbapiCols:
        strlist.append(json[key])
        
    return pd.Series(strlist, index = omdbapiCols, name = json['Title'])

def main():
    # configure requests to retry when there is an error
    session = rq.Session()
    session.mount("http://", rq.adapters.HTTPAdapter(max_retries=1))
    session.mount("https://", rq.adapters.HTTPAdapter(max_retries=1))

    # set up database
    engine = create_engine('mysql://root:@localhost/moviedb?charset=utf8', encoding = 'utf-8')
    
    df1 = pd.DataFrame()
    df2 = pd.DataFrame()
    replace = True
    for page in np.arange(100)+1:   # number of pages hardcoded here
        print 'Getting page: %d' % page
        time.sleep(0.5) # wait first, to be polite
        ids = get_movie_ids(page, session)   # ids = ['tt0468569']#, 'tt0241527']
        
        for id in ids:
            time.sleep(0.5)
            print 'Trying ID: %s' % id
            s1 = get_movie_info(id, session)
            if 'imdb_id' in s1.index:
                if re.search(r'^tt\d{7}$', s1['imdb_id']):
                    imdbid = s1['imdb_id']
                    df1 = df1.append(s1)
                    s2 = get_movie_scores(imdbid, session)
                    if not s2.empty: df2 = df2.append(s2)
                else: print 'Invalid imdb_id: %s' % s1['imdb_id']
            else: print 'No imdb_id key found'
            
        # do some conditioning before saving (avoids an issue with saving an index)
        df1['Title'] = df1.index
        df2['Title'] = df2.index
    
        # store in database after each loop iteration, in case something breaks
        if replace:
            temp = 'replace'
            replace = False
        else: temp = 'append'
        df1.to_sql('themoviedb', engine, if_exists = temp, index = False)
        df2.to_sql('omdb', engine, if_exists = temp, index = False)
        
        # empty data frames from memory
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
    
if __name__ == '__main__':
    main()
