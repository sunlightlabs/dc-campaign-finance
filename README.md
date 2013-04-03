# 2013 DC Council Special Election

Data and maps and fun for the DC Council's at-large seat.

The candidates:

* Anita Bonds
* Michael Brown
* Matthew Frumin
* Patrick Mara
* Perry Redd
* Elissa Silverman
* Paul Zukerberg


## Scripts and Data

*scrape-committees.py* will pull committee and candidate names from the DC Office of Campaign Finance web site and write them to *data/committee-candidate.csv*.

*process.py* turns the raw data found in *data/raw/contributions.csv* into geocoded, cleaned up data records written to *data/raw/contributions-geocoded.csv*. The script also creates a limited CSV of special election contributions at *data/special-election/all.csv*. The special election data is also split into per-candidate files at *data/special-election/<candidate slug>.csv*.
