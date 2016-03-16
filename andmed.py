#!/usr/bin/env python3
import csv
import os
import re
from collections import namedtuple
from functools import reduce
from xml.etree import ElementTree

NAMESPACE = "http://www.talkbank.org/ns/talkbank"
ElementTree.register_namespace('', NAMESPACE)

UNKNOWN_RE = re.compile(r'#{4,}')
AGE_RE = re.compile(r'(\d+)Y')

ROW_FIELDS = [
    'corpus',
    'child_name',
    'child_age',
    'child_words',
    'child_analyzed',
    'child_unknown',
    'mot_words',
    'mot_analyzed',
    'mot_unknown'
]
Row = namedtuple('Row', ROW_FIELDS)


class NoChildException(Exception):
    pass


def get_tag(tag):
    return "{%s}%s" % (NAMESPACE, tag)


def parse_age(age):
    match = AGE_RE.search(age)
    return int(match.group(1))


def get_info(participant):
    participant_name = participant.get("name")
    participant_age = participant.get("age")
    return participant_name, parse_age(participant_age)


def get_child(root):
    for participant in root.findall(get_tag('Participants')):
        for p in participant:
            roll = p.get('role')
            if roll in ("Target_Child", "Child"):
                return get_info(p)
    raise NoChildException


def is_analyzed(word):
    for mor in word.findall(get_tag("mor")):
        mw = mor.find(get_tag("mw"))
        pos = mw.find(get_tag("pos"))
        c = pos.find(get_tag("c"))
        if not UNKNOWN_RE.match(c.text):
            return True
    return False


def process_words_in_element(element):
    words, analyzed, unknown = 0, 0, 0
    for w in element.findall(get_tag('w')):
        words += 1
        replacement = w.find(get_tag('replacement'))
        if replacement:
            w = replacement.find(get_tag("w"))

        if is_analyzed(w):
            analyzed += 1
        else:
            unknown += 1
    return words, analyzed, unknown


def handle_utterance(utterance):
    results = [process_words_in_element(utterance)]
    for g in utterance.findall(get_tag('g')):
        results.append(process_words_in_element(g))
    return results


def sum_results(results):
    """
    :param results: [(words1, analyzed1, unknown1), (words2, analyzed2, unknown2), ...]
    :return: (total_words, total_analyzed, total_unknown)
    """
    def s(t1, t2):
        return t1[0]+t2[0], t1[1]+t2[1], t1[2]+t2[2]
    return reduce(s, results, (0, 0, 0))


def read_file(src_path):
    tree = ElementTree.parse(src_path)
    root = tree.getroot()
    chi_name, chi_age = get_child(root)
    corpus = os.path.basename(os.path.dirname(src_path))

    chi_results = []
    mot_results = []

    for u in root.findall(get_tag('u')):
        results = handle_utterance(u)
        if u.get("who") == "CHI":
            chi_results.extend(results)
        else:
            mot_results.extend(results)

    chi_words, chi_analyzed, chi_unknown = sum_results(chi_results)
    mot_words, mot_analyzed, mot_unknown = sum_results(mot_results)

    return Row(
        corpus, chi_name, chi_age,
        chi_words, chi_analyzed, chi_unknown,
        mot_words, mot_analyzed, mot_unknown
    )


if __name__ == '__main__':
    srcdir = 'andmed'

    with open('data.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter='\t')
        writer.writerow(ROW_FIELDS)

        for subdir, dirs, files in os.walk(srcdir):
            for file in files:
                xml_path = os.path.join(subdir, file)
                try:
                    row = read_file(xml_path)
                except NoChildException:
                    print("No child in chat %r" % xml_path)
                    continue
                print(row)
                writer.writerow(row)