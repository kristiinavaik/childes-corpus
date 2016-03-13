#!/usr/bin/env python3
import os
import re
import shlex
from collections import namedtuple
from subprocess import Popen, PIPE
from xml.etree import ElementTree as ET

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x):
        return x

NAMESPACE = "http://www.talkbank.org/ns/talkbank"
ET.register_namespace('', NAMESPACE)


MorfAnalyys = namedtuple('MorfAnalyys', ['stem', 'pos'])


def get_tag(tag):
    return "{%s}%s" % (NAMESPACE, tag)


class Unintelligible(Exception):
    def __init__(self, word):
        self.word = word
        super(Unintelligible, self).__init__()


class Analysaator(object):

    MORF_RE = re.compile(
        r'^ \s* (?P<stem>[^\s]+) \s+ // (?P<pos>.+) \s* $',
        re.VERBOSE
    )
    SUFFIX_RE = re.compile(r', $')

    def __init__(self, etana_path, dct_path):
        self._analyysid = {}
        self._cmd = '%s -path %s' % (etana_path, dct_path)

    def _call_etana(self, word):
        p = Popen('echo %s | %s' % (shlex.quote(word), self._cmd), shell=True, stdout=PIPE)
        output, _ = p.communicate()
        output = output.decode()
        parts = output.split('\n')
        analyys = parts[1]

        match = self.MORF_RE.match(analyys)
        if not match:
            # sys.stderr.write("Invalid analyys for %r -> %r\n" % (word, analyys))
            return None
        pos = re.sub(r'(,\s*)?//$', '', match.group('pos'))
        return MorfAnalyys(match.group('stem'), pos)

    def analyysi(self, word):
        analyys = self._analyysid.get(word)
        if analyys:
            if isinstance(analyys, Unintelligible):
                raise analyys
            return analyys

        morf_analyys = self._call_etana(word)
        if morf_analyys is None:
            error = Unintelligible(word)
            self._analyysid[word] = error
            raise error
        self._analyysid[word] = morf_analyys
        return morf_analyys

    def _add_morf_elements(self, word):
        if not word.text:
            return

        try:
            morf_analyys = self.analyysi(word.text)
        except Unintelligible:
            if word.text.lower() == 'xxx':
                word.set('untranscribed', "unintelligible")
            morf_analyys = MorfAnalyys('####', '####')

        mor = ET.SubElement(word, 'mor')
        mor.set('type', 'mor')
        mw = ET.SubElement(mor, 'mw')

        pos = ET.SubElement(mw, 'pos')
        c = ET.SubElement(pos, 'c')

        c.text = morf_analyys.pos
        stem = ET.SubElement(mw, 'stem')
        stem.text = morf_analyys.stem

    def add_morf_to_xml(self, src_path, result_path):
        tree = ET.parse(src_path)
        root = tree.getroot()
        for utterance in root.findall(get_tag('u')):
            for w in utterance.findall(get_tag('w')):
                replacement = w.find(get_tag('replacement'))
                if replacement:
                    for replacement_word in replacement.findall(get_tag('w')):
                        self._add_morf_elements(replacement_word)
                    continue
                self._add_morf_elements(w)

        tree.write(result_path, 'utf-8')


if __name__ == '__main__':
    analysaator = Analysaator('etana/etana', 'etana')
    src_dir = os.path.join('xml_files', 'Vija')
    result_dir = os.path.join(src_dir, 'with_morf')
    os.makedirs(result_dir, exist_ok=True)
    for f in tqdm(os.listdir(src_dir)):
        if not f.endswith('.xml'):
            continue
        analysaator.add_morf_to_xml(os.path.join(src_dir, f), os.path.join(result_dir, f))
