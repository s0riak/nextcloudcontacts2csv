#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) 2017 Sebastian Kanis
# This file is part of nextcloudcontacts2csv.
# nextcloudcontacts2csv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# nextcloudcontacts2csv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with nextcloudcontacts2csv.  If not, see <http://www.gnu.org/licenses/>.
import argparse

import logging
from mysql.connector import MySQLConnection, Error
import MySQLdb as mdb
import sys
import re
import csv
from dateutil.parser import parse
import chardet

def get_date_from_string(data):
    pattern = re.compile("^\d{4}-\d{2}-\d{2}$")
    if pattern.match(data):
        return {"year": int(data[:4]), "month": int(data[5:7]), "day": int(data[8:10])}
    pattern = re.compile("^\d{8}$")
    if pattern.match(data):
        return {"year": int(data[:4]), "month": int(data[4:6]), "day": int(data[6:8])}
                                
def get_dict_from_vcard(vCard):
    result = {}
    lines = vCard.splitlines()
    for index, line in enumerate(lines):
        line = line.decode('utf8')
        if line.startswith("UID:"):
            result["uid"] = line[4:]
        if line.startswith("REV:"):
            result["rev"] = parse(line[4:])
        if line.startswith("ADR;"):
            if not "address" in result:
                result["address"] = []
            address = {}
            parts=line.split(";")
            if parts[1].startswith("TYPE="):
                address["type"] = parts[1].split(":")[0][5:]
            address["street"] = parts[3]
            address["city"] = parts[4]
            address["zip"] = parts[6]
            address["country"] = parts[7]
            result["address"].append(address)
        if line.startswith("FN:"):
            result["fullName"] = line[3:]
        if line.startswith("N:"):
            parts = line[2:].split(";")
            result["lastName"] = parts[0]
            result["firstName"] = parts[1]
        if line.startswith("EMAIL;"):
            if not "email" in result:
                result["email"] = []
            email = {}
            parts=line.split(";")
            if parts[1].startswith("TYPE="):
                email["type"] = parts[1].split(":")[0][5:]
                email["address"] = parts[1].split(":")[1]
            result["email"].append(email)
        if line.startswith("CATEGORIES:"):
            if not "categories" in result:
                result["categories"] = []
            parts = line[11:].split(",")
            for part in parts:
                result["categories"].append(part)
        if line.startswith("BDAY:"):
            result["birthday"] = get_date_from_string(line[5:])
        if line.startswith("NOTE:"):
            notes = line[5:].replace("\,", ",").replace("\\n", " ")
            i = index+1
            while i < len(lines) and lines[i].decode('utf8').startswith(" "):
                notes = notes + lines[i][1:].decode('utf8').replace("\,", ",").replace("\\n", " ")
                i = i + 1
            result["notes"] = notes.split("\;")
        if line.startswith("TEL;"):
            if not "phone" in result:
                result["phone"] = []
            phone = {}
            parts=line.split(";")
            if parts[1].startswith("TYPE="):
                phone["type"] = parts[1].split(":")[0][5:]
                if len(parts[1].split(":")) == 2:
                    phone["number"] = parts[1].split(":")[1]
                #TODO handle more complex numbers like TEL;TYPE=cell;PREF=1:11833
            result["phone"].append(phone)
    return result

def load_raw_from_db(hostname, username, password, dbname):
    cursor = None
    con = None
    try:
        #con = mdb.connect('localhost', 'nextcloud', 'eezahD7P', 'nextcloud');
        con = mdb.connect(hostname, username, password, dbname);
        cursor = con.cursor()
        cursor.execute("SELECT oc_cards.carddata FROM oc_cards WHERE addressbookid=3")
        rows = cursor.fetchall()
        return rows
    except Error as e:
        logging.getLogger("main").error("failed to load data from database" + str(e))
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()

def get_contact_with_uid(contacts, uid):
    for index, contact in enumerate(contacts):
        if contact["uid"] == uid:
            return index
    return None

def parse_data(raw):
    result = []
    for row in raw:
        candidate = get_dict_from_vcard(row[0])
        index = get_contact_with_uid(result, candidate["uid"])
        if index is not None:
            if candidate["rev"] > result[index]["rev"]:
                result[index] = candidate
        else:
            result.append(candidate)
    return result

def get_attribute_of_type(contact, attributeName, attributeType, valueKey):
    if not attributeName in contact:
        return None
    else:
        for attribute in contact[attributeName]:
            if attribute["type"].lower() == attributeType.lower():
                if valueKey in attribute:
                    return attribute[valueKey]
        return None

def get_preferred_attribute(contact, attributeName, valueKey, preferenceList, getOther=True):
    for preference in preferenceList:
        attribute = get_attribute_of_type(contact, attributeName, preference, valueKey)
        if not attribute == None:
            return attribute
    if getOther and attributeName in contact:
        if len(contact[attributeName]) > 0:
            return contact[attributeName][0][valueKey]
    return ""

def unicode_object_to_utf8string(object):
    if isinstance(object, dict):
        result = "{"
        first = True
        for key in object.keys():
            if first:
                first = False
            else:
                result += ", "
            result += key + ":" + unicode_object_to_utf8string(object[key])
        result += "}"
        return result
    elif isinstance(object, list):
        result = "["
        first = True
        for item in object:
            if first:
                first = False
            else:
                result += ", "
            result += unicode_object_to_utf8string(item)
        result += "]"
        return result
    elif isinstance(object, unicode):
        return object.encode('ascii', 'ignore')
    elif object is None:
        return "None"
    else:
        return str(object)

def string_contained_in_list(string, list_of_strings):
    for list_item in list_of_strings:
        if string == list_item:
            return True
    return False

def include_in_export(contact, relevant_categories):
    if not "categories" in contact:
        logging.getLogger("main").debug("contact " + str(contact) + " not included (categories missing)")
        return False
    for relevant_category in relevant_categories:
        if string_contained_in_list(relevant_category, contact["categories"]):
            logging.getLogger("main").debug("contact " + str(contact) + " included (category '" + relevant_category + "'found)")
            return True
    logging.getLogger("main").debug(
            "contact " + str(contact) + " has categories '" + str(contact["categories"]) + "' not in  '" + str(relevant_category) + "' not in categories")
    return False

def get_max_number_of_notes(data, relevant_categories):
    number_of_notes = 0
    for item in data:
        if include_in_export(item, relevant_categories):
            if "notes" in item:
                number_of_notes = max(number_of_notes, len(item["notes"]))
    return number_of_notes

def write_data_to_csv(data, relevant_categories):

    with open('addresses.csv', 'w') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        header = ["firstName", "lastName", "birthday", "phoneNumber", "mail", "street", "zipcode", "city"]
        for index in range(0, get_max_number_of_notes(data, relevant_categories)):
            header.append("note_" + str(index))
        csvwriter.writerow(header)
        for item in data:
            if include_in_export(item, relevant_categories):
                try:
                    phoneNumber = get_preferred_attribute(item, "phone", "number", ["cell", "home", "work"])
                    mail = get_preferred_attribute(item, "email", "address", ["home", "work"])
                    if "birthday" in item:
                        birthday = str(item["birthday"]["day"]) + "." + str(item["birthday"]["month"]) + "." + str(item["birthday"]["year"])
                    else:
                        birthday = ""
                    street = get_preferred_attribute(item, "address", "street", ["home", "work"])
                    city = get_preferred_attribute(item, "address", "city", ["home", "work"])
                    zipcode = get_preferred_attribute(item, "address", "zip", ["home", "work"])
                    row = [item["firstName"], item["lastName"], birthday, phoneNumber, mail, street, zipcode, city]
                    note = []
                    if "notes" in item:
                        for note in item["notes"]:
                            row.append(note)
                    csvwriter.writerow(row)
                except KeyError as e:
                    logging.getLogger("main").error("KEYERROR: " + str(e) + " " + str(item))

def get_arguments():
    parser = argparse.ArgumentParser(description='This hacky piece extracts contacts from nextcloud and writes them to csv')
    parser.add_argument('-hn', '-hostname', help='hostname of the host on which the nextcloud database is running', required=True)
    parser.add_argument('-u', '-username', help='username to be used to connect to the database', required=True)
    parser.add_argument('-p', '-password', help='password to be used to connect to the database', required=True)
    parser.add_argument('-n', '-dbname', help='database name to be used to connect to the database', required=True)
    parser.add_argument('-c', '-categories', help='the categories/groups to be included in the export', default='')


    logLevelsRange = [logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR, logging.CRITICAL]
    parser.add_argument('-l', '-logLevel', help='the log level for output', type=int, choices=logLevelsRange,
                        default=logging.INFO)
    return vars(parser.parse_args())

def initLogging(consoleLogLevel):
    logger = logging.getLogger("main")
    logger.setLevel(consoleLogLevel)
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    consoleHandler.setLevel(consoleLogLevel)
    logger.addHandler(consoleHandler)
    logging.getLogger("main").log(consoleLogLevel, "logging initiated with level " + str(consoleLogLevel))

def main(args):
    initLogging(args['l'])
    logging.getLogger('main').debug("loading data...")
    raw = load_raw_from_db(args['hn'], args['u'], args['p'], args['n'])
    logging.getLogger('main').debug("loading data finished")
    logging.getLogger('main').debug("parsing data...")
    parsed = parse_data(raw)
    logging.getLogger('main').debug("parsing data finished")
    logging.getLogger('main').debug("writing data to csv...")
    write_data_to_csv(parsed, args['c'].split(","))
    logging.getLogger('main').debug("all finished")

#arguments are passed to main to be able to call main from a separate script containing the parameters
if __name__ == '__main__':
    args = get_arguments()
    main(args)
