from lxml import objectify
import os
import glob


def read_xml_file(file_path):
    with open(file_path) as file:
        return objectify.fromstring(file.read())


def read_xml_files(file_path):
    files = list()
    for file_name in file_path.split(';'):
        if os.path.isdir(file_name):
            xml_files = glob.glob(file_name + '/*.xml')
            for file in xml_files:
                files.append(read_xml_file(file))
        else:
            files.append(read_xml_file(file_name))

    return files