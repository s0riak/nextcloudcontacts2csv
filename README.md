# nextcloudcontacts2csv
This hacky piece extracts contacts from nextcloud and writes them to csv

## Output
generates a csv with one line per contact with the following columns
0. firstName	- the firstName (detailed name) needs to be filled
0. lastName	- the lastName (detailed name) needs to be filled
0. birthday	- the birthday is optional
0. phoneNumber - the phoneNumber of the contact (only "TEL;TYPE=cell:xyz"-type phonenumber entries are supported), if multiple phoneNumbers are provided, cell, home, work, is the preference order
0. mail	- the mailadress, if multiple phoneNumbers are provided, home, work, is the preference order
0. street	- the street of the adress, if multiple addresses are provided, home, work, is the preference order
0. zipcode - the zipcode of the adress, if multiple addresses are provided, home, work, is the preference order
0. city	- the city of the adress, if multiple addresses are provided, home, work, is the preference order
0. note_1 - the first part of the note (splitted by ";")
0. note_2 - the second part of the note (splitted by ";")

## Future DEV
Could be used to build a more generic tool to transform VCards to csv, but I just needed a quick way to extract some addresses. Everybody, who is willing to work with vCard (which is a pain), is encouraged to expand the functionality.
