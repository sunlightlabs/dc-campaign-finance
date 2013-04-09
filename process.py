import datetime
import os
import random
import re

from omgeo import Geocoder
from saucebrush import sources, filters, emitters, run_recipe
import unicodecsv as csv

PWD = os.path.abspath(os.path.dirname(__file__))

CANDIDATES = ('Matthew Frumin', 'Anita Bonds', 'Michael Brown',
              'Elissa Silverman', 'Perry Redd', 'Patrick Mara',
              'Paul Zukerberg')

FIELDNAMES = ('committee', 'candidate', 'contributor', 'contributor_type',
              'address', 'city', 'state', 'zip', 'lat', 'lon', 'amount',
              'date', 'contribution_type')


#
# utility methods
#

def rejigger_name(s):
    """ Change LAST, FIRST to FIRST LAST name format.
    """
    name_parts = s.split(',', 1)
    name = "%s %s" % (name_parts[1].strip(), name_parts[0].strip())
    return name


def currency_to_float(s):
    """ Convert a currency formateed number to a float.
    """
    s = re.sub(r"[^\d\.]", "", s)
    return float(s)


def pseudoslugify(s):
    """ Very basic slugification of strings. Remove non-alpha characters
        and replace spaces with hyphens.
    """
    s = s.lower()
    s = s.replace(' ', '-')
    s = re.sub(r'[^a-z\-]', '', s)
    return s


def candidate_path(s):
    """ Create a CSV path based on the slugified name of candidate.
    """
    slug = pseudoslugify(s)
    path = os.path.join(PWD, 'data', 'special-election', '%s.csv' % slug)
    return path


def parse_date(s):
    """ Parse string date format into a date object.
    """
    dt = datetime.datetime.strptime(s, '%m/%d/%y')
    return dt.date()


#
# saucebrush filters
#

class ContributorNameFilter(filters.Filter):
    """ Reformat contributor names for individuals.
    """

    def process_record(self, record):
        if record['contributor_type'] == 'Individual' and "," in record['contributor']:
            record['contributor'] = rejigger_name(record['contributor'])
        return record


class StateFixerFilter(filters.Filter):
    """ Add DC to records missing a state field when the city is Washington.
    """

    def process_record(self, record):
        if record['city'].upper() == 'WASHINGTON' and not record['state']:
            record['state'] = 'DC'
        return record


class CandidateFilter(filters.Filter):
    """ Add candidate name to record based on the committee that
        received the campaign contribution.
    """

    def __init__(self, *args, **kwargs):
        super(CandidateFilter, self).__init__(*args, **kwargs)
        self.committees = CandidateFilter.load_committees()

    @classmethod
    def load_committees(self):
        committees = {}
        path = os.path.join(PWD, 'data', 'committee-candidate.csv')
        with open(path) as infile:
            reader = csv.DictReader(infile)
            for record in reader:
                if record['committee'] != 'N/A':
                    committees[record['committee']] = rejigger_name(record['candidate'])
        return committees

    def process_record(self, record):
        record['candidate'] = self.committees.get(record['committee'])
        return record


class SpecialElectionCandidateFilter(filters.ConditionalFilter):
    """ Only allow candidates in the special election to pass.
    """

    def __init__(self, candidates):
        super(SpecialElectionCandidateFilter, self).__init__()
        self.candidates = candidates

    def test_record(self, record):
        return record['candidate'] in self.candidates


class DateFilter(filters.ConditionalFilter):
    """ Only allow contributions on or after the specified date to pass.
    """

    def __init__(self, date):
        super(DateFilter, self).__init__()
        self.date = date

    def test_record(self, record):
        record_date = parse_date(record['date'])
        return record_date >= self.date


class FakeGeocodingFilter(filters.Filter):
    """ Generate fake coordinates within the provided bounding box.
    """

    def __init__(self, top_left, bottom_right, *args, **kwargs):
        super(FakeGeocodingFilter, self).__init__(*args, **kwargs)
        self.top_left = top_left
        self.bottom_right = bottom_right

    def make_coordinate(self):
        lat_diff = (self.top_left[0] - self.bottom_right[0]) * random.random()
        lon_diff = (self.top_left[1] - self.bottom_right[1]) * random.random()
        return (self.bottom_right[0] + lat_diff, self.bottom_right[1] + lon_diff)

    def process_record(self, record):
        coordinate = self.make_coordinate()
        record['lat'] = coordinate[0]
        record['lon'] = coordinate[1]
        return record


class GeocodingFilter(filters.Filter):
    """ Geocode contributions based on address.
    """

    def __init__(self, *args, **kwargs):
        super(GeocodingFilter, self).__init__(*args, **kwargs)
        self.geocoder = Geocoder()
        self.cache = {}

        with open(os.path.join(PWD, 'data', 'geocache.csv')) as infile:
            for record in csv.reader(infile):
                self.cache[record[0]] = (record[1], record[2])

    def process_record(self, record):

        if not record.get('lat') and not record.get('lon'):

            vals = (record['address'], record['city'], record['state'], record['zip'])
            addr = "%s %s %s %s" % vals

            if addr in self.cache:

                ll = self.cache[addr]
                record['lat'] = ll[0]
                record['lon'] = ll[1]

            else:

                result = self.geocoder.geocode(addr)

                candidates = result.get('candidates', None)
                if candidates:
                    c = candidates[0]

                    record['lat'] = c.y
                    record['lon'] = c.x

        return record


#
# saucebrush emitters
#

class CSVEmitterCache(object):

    def __init__(self, fieldnames):
        self.fieldnames = fieldnames
        self.files = {}
        self.emitters = {}

    def open(self, key, path, mode='r'):

        fp = open(path, mode)
        self.files[key] = fp

        emitter = emitters.CSVEmitter(fp, self.fieldnames)
        self.emitters[key] = emitter

        return emitter

    def get(self, key):
        return self.emitters.get(key)

    def close(self, key=None):
        if key:
            if key in list(self.emitters.keys()):
                del self.emitters[key]
            if key in list(self.files.keys()):
                self.files[key].close()
                del self.files[key]
        else:
            for key in list(self.files.keys()):
                self.close(key)


class CandidateEmitter(emitters.Emitter):

    def __init__(self, candidates):
        self.emitters = CSVEmitterCache(FIELDNAMES)
        self.candidates = dict((c, candidate_path(c)) for c in candidates)
        for (key, path) in self.candidates.items():
            self.emitters.open(key, path, 'w')

    def emit_record(self, record):
        emitter = self.emitters.get(record['candidate'])
        if emitter:
            emitter.emit_record(record)

    def done(self):
        self.emitters.close()


if __name__ == '__main__':

    field_mapping = {
        'committee': 'Committee Name',
        'contributor': 'Contributor',
        'contributor_type': 'Contributor Type',
        'contribution_type': 'Contribution Type',
        'address': 'Address',
        'zip': 'Zip',
        'amount': 'Amount',
        'date': 'Date of Receipt',
    }

    raw_path = os.path.join(PWD, 'data', 'raw', 'contributions.csv')
    geocoded_path = os.path.join(PWD, 'data', 'raw', 'contributions-geocoded.csv')
    atlarge_path = os.path.join(PWD, 'data', 'special-election', 'all.csv')

    # geocode contributions

    # with open(raw_path) as infile:
    #     with open(geocoded_path, 'w') as geocoded_file:
    #         run_recipe(
    #             sources.CSVSource(infile),
    #             filters.FieldRenamer(field_mapping),
    #             filters.FieldAdder('lat', ''),
    #             filters.FieldAdder('lon', ''),
    #             filters.FieldAdder('candidate', ''),
    #             filters.FieldModifier('amount', currency_to_float),
    #             StateFixerFilter(),
    #             CandidateFilter(),
    #             ContributorNameFilter(),
    #             # FakeGeocodingFilter((39.635307, -77.865601), (38.169114, -75.937500)),
    #             GeocodingFilter(),
    #             emitters.CountEmitter(every=100),
    #             emitters.CSVEmitter(geocoded_file, FIELDNAMES),
    #             error_stream=emitters.DebugEmitter()
    #         )

    # limit to special election contributions and split into candidate files

    # with open(geocoded_path) as infile:
    #     with open(atlarge_path, 'w') as atlarge_file:
    #         run_recipe(
    #             sources.CSVSource(infile),
    #             SpecialElectionCandidateFilter(CANDIDATES),
    #             DateFilter(datetime.date(2012, 11, 28)),
    #             CandidateEmitter(CANDIDATES),
    #             emitters.CountEmitter(every=100),
    #             emitters.CSVEmitter(atlarge_file, FIELDNAMES),
    #             error_stream=emitters.DebugEmitter()
    #         )

    # extract geocoded locations

    geocache_path = os.path.join(PWD, 'data', 'geocache.csv')

    with open(geocoded_path) as infile:
        with open(geocache_path, 'w') as outfile:
            run_recipe(
                sources.CSVSource(infile),
                filters.FieldMerger({'address': ('address', 'city', 'state', 'zip')},
                                    lambda a, c, s, z: "%s %s %s %s" % (a, c, s, z)),
                filters.FieldKeeper(('address', 'lat', 'lon',)),
                emitters.CSVEmitter(outfile, ('address', 'lat', 'lon')),
                error_stream=emitters.DebugEmitter()
            )
