''' Script for detecting new legislators and getting as much data as possible about them. '''

import csv
import urllib
import re
from collections import defaultdict
#from votesmart import votesmart, VotesmartApiError
# set votesmart api key here

STATES = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
          'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
          'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
          'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
          'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
NONSTATES = ['DC', 'PR', 'GU', 'VI', 'AS', 'MP']

def get_votesmart_legislators():
    for state in STATES:
        try:
            for leg in votesmart.officials.getByOfficeState(6, state):
                yield leg
        except VotesmartApiError:
            pass

        for leg in votesmart.officials.getByOfficeState(5, state):
            yield leg

class LegislatorTable(object):

    def __init__(self):
        self.csvfile = 'legislators.csv'
        self.legislators = {}
        for line in csv.DictReader(open(self.csvfile)):
            self.legislators[line['bioguide_id']] = line

    def get_legislator(self, attname, value):
        for leg in self.legislators.itervalues():
            if leg[attname] == value:
                return leg

    def get_legislators(self, attname, value):
        for leg in self.legislators.itervalues():
            if leg[attname] == value:
                yield leg

    def sanity_check(self):
        sens = defaultdict(list)
        reps = defaultdict(list)
        dels = defaultdict(list)

        # go through entire list and count active legislators
        for leg in self.get_legislators('in_office', '1'):
            if leg['title'] == 'Sen':
                sens[leg['state']].append(leg['district'])
            elif leg['title'] == 'Rep':
                reps[leg['state']].append(leg['district'])
            else:
                dels[leg['state']].append(leg['district']) 

        # senators
        for state, districts in sens.iteritems():
            if len(districts) > 2:
                print state, 'has %d senators' % len(districts)
            if 'Junior Seat' not in districts:
                print state, 'has no Junior Senator'
            if 'Senior Seat' not in districts:
                print state, 'has no Senior Senator'

        # representatives
        for state, districts in reps.iteritems():
            num_reps = len(districts)
            districts = sorted(int(x) for x in districts)
            expected = range(1, num_reps+1) if num_reps > 1 else [0]
            if districts != expected:
                print state, 'has districts:', str(districts)

        # delegates
        delstates = dels.keys()
        diffs = set(delstates).symmetric_difference(set(NONSTATES))
        if diffs:
            print 'missing delegates from: %s' % (','.join(diffs))


    def check_bioguide(self):

        # get maximum ids 
        max_ids = {}
        for id in sorted(self.legislators.iterkeys()):
            max_ids[id[0]] = id

        # so that if any Q X or Z legislators are elected we'll know
        max_ids.setdefault('Q', 'Q000022')
        max_ids.setdefault('X', 'X000000')
        max_ids.setdefault('Z', 'Z000016')

        # check all urls finding non-tracked bioguide ids
        for letter, max_id in max_ids.iteritems():
            id_num = int(max_id[1:], 10)+1

            while True:
                url = 'http://bioguide.congress.gov/scripts/biodisplay.pl?index=%s%06d' % (letter, id_num)
                page = urllib.urlopen(url).read()
                if re.search('does not exist', page):
                    break
                print '%s%06d' % (letter, id_num),
                results = re.search('<a name="Top">(\w+), (\w+).+</a>', page)
                if results:
                    last, first = results.groups()
                    print first, last
                else:
                    print '--check manually--'
                id_num += 1

    def check_new_legislators(self, add=False):
        for leg in get_votesmart_legislators():
            if not self.get_legislator(votesmart_id=leg.candidateId):
                print '%s %s (%s)' % (leg.firstName, leg.lastName, leg.candidateId)
            if add:
                bioguide = raw_input('Bioguide ID: ')
                if bioguide:
                    self.add_legislator(leg, bioguide_id=bioguide)

