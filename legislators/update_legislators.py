''' Script for detecting new legislators and getting as much data as possible about them. '''

import csv
import urllib
import re
from collections import defaultdict
#from votesmart import votesmart, VotesmartApiError
#votesmart.apikey = '496ec1875a7885ec65a4ead99579642c'

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

    def __init__(self, filename):
        self.csvfile = filename
        self.legislators = {}
        reader = csv.DictReader(open(self.csvfile))
        for line in reader:
            self.legislators[line['bioguide_id']] = line
        self.fieldnames = reader.fieldnames

    def save_to(self, filename):
        writer = csv.DictWriter(open(filename, 'w'), self.fieldnames, 
                                quoting=csv.QUOTE_ALL)
        # write header
        writer.writerow(dict(zip(self.fieldnames, self.fieldnames)))
        for key in sorted(self.legislators.iterkeys()):
            writer.writerow(self.legislators[key])

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

    def add_legislator(self, official, bioguide_id):
        person = {}
        # get basic information
        id = person['votesmart_id'] = official.candidateId
        person['firstname'] = official.firstName
        person['middlename'] = official.middleName
        person['lastname'] = official.lastName
        person['name_suffix'] = official.suffix
        person['nickname'] = official.nickName
        person['title'] = official.title[0:3]
        state = person['state'] = official.officeStateId
        district = person['district'] = official.officeDistrictName
        person['party'] = official.officeParties[0]

        # get information from address
        try:
            offices = votesmart.address.getOffice(id)
            for office in offices:
                if office.state == 'DC':
                    person['congress_office'] = office.street
                    person['phone'] = office.phone1
                    person['fax'] = office.fax1
        except VotesmartApiError:
            pass

        # get information from web address
        webaddr_re = re.compile('.+(house|senate)\.gov.+')
        try:
            webaddrs = votesmart.address.getOfficeWebAddress(id)
            for webaddr in webaddrs:
                if webaddr.webAddressType == 'Website' and webaddr_re.match(webaddr.webAddress):
                    person['website'] = webaddr.webAddress
                elif webaddr.webAddressType == 'Webmail' and webaddr_re.match(webaddr.webAddress):
                    person['webform'] = webaddr.webAddress
                elif webaddr.webAddressType == 'Email' and webaddr_re.match(webaddr.webAddress):
                    person['email'] = webaddr.webAddress
        except VotesmartApiError:
            pass

        # get information from bio
        bio = votesmart.candidatebio.getBio(id) 
        if bio.gender:
            person['gender'] = bio.gender[0]
        person['fec_id'] = bio.fecId
        
        try:
            curleg = Legislator.objects.get(state=state,district=district,
                                               in_office=True)
            print 'Setting in_office=False on:', curleg
            curleg.in_office = False
            curleg.save()
        except ObjectDoesNotExist:
            pass
        
        person['bioguide_id'] = bioguide_id
        # person['crp_id'] =
        # person['govtrack_id'] =
        # person['twitter_id'] =
        # person['congresspedia_url'] =
        
        Legislator.objects.create(**person)

def compare_to(oldfile, newfile, approved_edits=None):
    old = LegislatorTable(oldfile)
    new = LegislatorTable(newfile)
    if approved_edits is None:
        approved_edits = []

    new_attributes = set()
    changes = defaultdict(set)

    for bio_id, new_leg in new.legislators.iteritems():
        if bio_id not in old.legislators:
            print 'New Legislator:', bio_id
        else:
            this_leg = old.legislators[bio_id]
            for k,v in new_leg.iteritems():
                if k not in this_leg:
                    new_attributes.add(k)
                elif this_leg[k] != v:
                    changes[bio_id].add(k)

    # print results
    print 'New Attributes:', ' '.join(new_attributes)
    for leg, changed_keys in changes.iteritems():
        old_leg = old.legislators[leg]
        new_leg = new.legislators[leg]
        print leg, old_leg['firstname'], old_leg['lastname']
        for key in changed_keys:
            print '\t%s: %s -> %s' % (key, old_leg[key], new_leg[key])
            if key in approved_edits:
                old.legislators[leg][key] = new_leg[key]

    old.save_to(oldfile)

