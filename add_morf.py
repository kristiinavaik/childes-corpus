#!/usr/bin/env python3
import os
import re
import shlex
from subprocess import Popen, PIPE
from xml.etree import ElementTree as ET

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x):
        return x

NAMESPACE = "http://www.talkbank.org/ns/talkbank"
ET.register_namespace('', NAMESPACE)


def get_tag(tag):
    return "{%s}%s" % (NAMESPACE, tag)


class Unintelligible(Exception):
    def __init__(self, word):
        self.word = word
        super(Unintelligible, self).__init__()


class Analysaator(object):

    MORF_RE = re.compile(r'\s{4}([^/]+)\s//([^/]+) ')

    def __init__(self, etana_path='etana', dct_path='', etfs2gt_path='etfs2gt'):
        self._analyysid = {}
        self._cmd = '%s | %s' % (etana_path, etfs2gt_path)
        if dct_path:
            self._cmd = '%s -path %s | %s' % (etana_path, dct_path, etfs2gt_path)

    def _call_etana(self, word):
        """
        :param word: string
        :return: matches, [(stem: string, pos: string), ...]
        """
        p = Popen('echo %s | %s' % (shlex.quote(word), self._cmd), shell=True, stdout=PIPE)
        output, _ = p.communicate()
        output = output.decode()

        matches = self.MORF_RE.findall(output)
        if not matches:
            # sys.stderr.write("Invalid analyys for %r -> %r\n" % (word, analyys))
            return None
        return matches

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
            morf_analyys = [('####', '####')]

        for stem, pos in morf_analyys:
            mor = ET.SubElement(word, 'mor')
            mor.set('type', 'mor')
            mw = ET.SubElement(mor, 'mw')

            pos_element = ET.SubElement(mw, 'pos')
            c_element = ET.SubElement(pos_element, 'c')
            c_element.text = pos.rstrip(',')
            stem_element = ET.SubElement(mw, 'stem')
            stem_element.text = stem

    def _handle_w_tag(self, element):
        for w in element.findall(get_tag('w')):
            replacement = w.find(get_tag('replacement'))
            if replacement:
                for replacement_word in replacement.findall(get_tag('w')):
                    self._add_morf_elements(replacement_word)
                continue
            self._add_morf_elements(w)

    def _handle_g_tag(self, element):
        for g in element.findall(get_tag('g')):
            self._handle_w_tag(g)
            self._handle_g_tag(g)

    def add_morf_to_xml(self, src_path, result_path):
        tree = ET.parse(src_path)
        root = tree.getroot()
        for utterance in root.findall(get_tag('u')):
            self._handle_w_tag(utterance)
            self._handle_g_tag(utterance)

        tree.write(result_path, 'utf-8')


# if __name__ == '__main__':
#     analysaator = Analysaator()
#     src_dir = os.path.join('xml_files', 'Korgesaar')
#     result_dir = os.path.join(src_dir, 'with_morf')
#     os.makedirs(result_dir, exist_ok=True)
#     for f in tqdm(os.listdir(src_dir)):
#         if not f.endswith('.xml'):
#             continue
#         analysaator.add_morf_to_xml(os.path.join(src_dir, f), os.path.join(result_dir, f))


if __name__ == '__main__':
    analysaator = Analysaator()
    src_dirs = [os.path.join('xml_files', src_dir) for src_dir in os.listdir('xml_files')]
    for src_dir in src_dirs:
        result_dir = os.path.join(src_dir, 'with_morf')
        os.makedirs(result_dir, exist_ok=True)
        for f in tqdm(os.listdir(src_dir)):
            if not f.endswith('.xml'):
                continue
            analysaator.add_morf_to_xml(os.path.join(src_dir, f), os.path.join(result_dir, f))
