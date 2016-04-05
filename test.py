#!/usr/bin/env python3

import os
import shlex
from subprocess import check_output
from xml.etree import ElementTree

import andmed
from tqdm import tqdm


def get_words_analyze(element):
    for word in element.findall(andmed.get_tag('w')):
        replacement = word.find(andmed.get_tag('replacement'))
        if replacement:
            word = replacement.find(andmed.get_tag("w"))

        for mor in word.findall(andmed.get_tag("mor")):
            mw = mor.find(andmed.get_tag("mw"))
            pos = mw.find(andmed.get_tag("pos"))
            c = pos.find(andmed.get_tag("c"))
            stem = mw.find(andmed.get_tag("stem"))

            if andmed.UNKNOWN_RE.match(c.text):
                yield (word.text, "%s    ####" % word.text)
            else:
                stem_pos = ("%s //%s //" % t for t in zip(stem.text.split('; '), c.text.split('; ')))
                result = "%s    %s" % (word.text, "    ".join(stem_pos))
                yield (word.text, result.strip())


def get_analysis_from_utterance(utterance):
    results = list(get_words_analyze(utterance))
    for g in utterance.findall(andmed.get_tag('g')):
        results.extend(get_words_analyze(g))
    return results


def read_file(path):
    tree = ElementTree.parse(path)
    root = tree.getroot()
    analysis = []
    for u in root.findall(andmed.get_tag('u')):
        analysis.extend(get_analysis_from_utterance(u))
    return analysis


def main():
    paths = []
    for root, dirs, files in os.walk('.'):
        if os.path.basename(root) == 'with_morf':
            paths.extend([os.path.join(root, f) for f in files])

    with open('from_xml.txt', 'w') as from_xml, open('from_etana.txt', 'w') as from_etana:
        for path in tqdm(paths):
            for word, analyze in read_file(path):
                etana_output = check_output('echo %s | etana | etfs2gt' % shlex.quote(word), shell=True).decode().strip()

                from_xml.write('%s\n' % analyze)
                from_etana.write('%s\n' % etana_output)
                assert etana_output == analyze, "Expected %r,\ngot %r" % (analyze, etana_output)

if __name__ == '__main__':
    main()
