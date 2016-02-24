#!/usr/bin/env python3

import os
import re
import string
import time
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

TEMPLATE_ENV = Environment(loader=FileSystemLoader('.'))
TEMPLATE = TEMPLATE_ENV.get_template('template.xml')


class Event(object):

    MAPPING = {
        '[!!]':  'Contrastive Stressing',
        '[!]':   'Stressing',
        '[*]':   'Error Marking',
        '[///]': 'Reformulation',
        '[//]':  'Retracing',
        '[/]':   'Repetition',
        '[<]':   'Overlap Precedes',
        '[=!':   'Paralinguistic Material',
        '[>]':   'Overlap Follows',
        '[?]':   'Best Guess',
        '[+':    'Postcodes',
        '[%':    'Comment on Main Line',
        '[=':    'Explanation',
        '[:':    'Replacement',
        '[=?':   'Alternative Transcription',
        '[^':    'Complex Local Event',
        '[x':    'Multiple Repetition',
    }

    def __init__(self, pattern):
        self.pattern = pattern

    def is_word_event(self):
        return not self.pattern.startswith('[^')

    @property
    def xml(self):
        if not self.is_word_event():
            return '<freecode>%s</freecode>' % self.pattern
        raise NotImplemented

    def __str__(self):
        return self.pattern

    def __repr__(self):
        return str(self)


class Word(object):

    def __init__(self, word):
        self.word = word.strip()
        self.events = []

    @classmethod
    def extract_words(cls, words_string):
        parts = re.split(r'(\[[^\]]+\])', words_string)
        words = []
        utterance_events = []
        for part in parts:
            # print(words_string, part)
            if part.startswith('['):
                event = Event(part)
                if event.is_word_event():
                    words[-1].events.append(event)
                else:
                    utterance_events.append(event)
            else:
                words.extend([Word(w) for w in part.split() if w])
        return words, utterance_events

    def _get_punctuation_xml(self):
        punctuation_type = {
            '.': 'p',
            '!': 'e',
            '?': 'q',
            ',': 'comma'
        }.get(self.word)
        if not punctuation_type:
            raise ValueError('Unknown punctuation %r' % self.word)
        if punctuation_type == 'comma':
            return '<tagMarker type="comma"></tagMarker>'
        return '<t type="%s"></t>' % punctuation_type

    @property
    def xml(self):
        if self.word == '(.)':
            return '<pause symbolic-length="simple"/>'
        if self.word in string.punctuation:
            return self._get_punctuation_xml()
        return '<w>%s</w>' % self

    def __str__(self):
        if self.events:
            return "%s %s" % (self.word, ', '.join(map(str, self.events)))
        return self.word

    def __repr__(self):
        return str(self)


class Participant(object):

    ATTRIBUTES = (
        'age',
        'corpus',  # ?
        'custom',  # doesn't occur
        'education',  # doesn't occur
        'group',
        'language',
        'role',
        'SES',
        'sex'
    )

    _age_patt = re.compile(r'(\d+);(\d+).(\d+)')

    def __init__(self, *args):
        self.id = args[0]
        self.role = args[-1]
        if len(args) > 2:
            self.name = args[1]
        else:
            self.name = ''

        for a in self.ATTRIBUTES:
            setattr(self, a, '')

    def _format_age(self, age):
        match = self._age_patt.match(age)
        if not match:
            return ''
        years, months, days = match.groups()
        return 'P%dY%dM%dD' % (int(years), int(months), int(days))

    def set_meta(self, meta_list):
        self.language = meta_list[0]
        self.corpus = meta_list[1]
        self.age = self._format_age(meta_list[3])
        self.sex = meta_list[4]
        self.group = meta_list[5]
        self.SES = meta_list[6]
        self.role = meta_list[7]
        self.education = meta_list[8]
        self.custom = meta_list[9]
        self._validate()

    def _validate(self):
        assert self.id
        assert self.role
        assert self.language

    def __str__(self):
        values = [(attr, getattr(self, attr)) for attr in self.ATTRIBUTES]
        return ', '.join(['%s: %s' % (attr, value) for (attr, value) in values if value])

    def __repr__(self):
        return 'Participant<%s>' % self


class UtteranceComment(object):

    COMMENT_RE = re.compile(r'^%(?P<type>[^:]+):\s+(?P<comment>.*)')

    def __init__(self, line):
        comment_match = self.COMMENT_RE.match(line)
        if not comment_match:
            raise ValueError("Invalid comment on line: %r" % line)
        self.type = comment_match.group('type')
        self.value = comment_match.group('comment')

    @property
    def xml_type(self):
        xml_type = {
            'act': 'actions',
            'add': 'addressee',
            'com': 'comments',
            'err': 'errcoding',
            'exp': 'explanation',
            'par': 'paralinguistics',
        }.get(self.type)
        if self.type is None:
            raise ValueError("Invalid UtteranceComment type %r" % self.type)
        return xml_type


class Utterance(object):

    LINE_RE = re.compile(r'^\*(?P<who>[^:]+):\s+(?P<words>.*)')

    def __init__(self, line):
        self._line = line
        self.who = ''
        self.comments = []
        self.words = []
        self._parse()

    def _parse(self):
        line_match = self.LINE_RE.match(self._line)
        if not line_match:
            raise ValueError("Invalid utterance on line: %r" % self._line)
        self.who = line_match.group('who')
        self.words, self.events = Word.extract_words(line_match.group('words'))

    def __str__(self):
        return self._line


class Chat(object):

    CHAT_ATTRIBUTES = (
        'Color_words',
        'Comment',
        'Date',
        'Font',
        'Languages',
        'Participants',
        'PID',
        'Situation',
        'Time_Duration'
    )
    VALID_ATTRIBUTES = CHAT_ATTRIBUTES + ('ID',)
    _OTHER_ATTRIBUTES = ('id', 'chat_path', 'corpus')

    _ignore_patt = re.compile(r'^@(Begin|End|UTF8)')

    def __init__(self, chat_path):
        self.id = os.path.splitext(os.path.basename(chat_path))[0]
        self.chat_path = chat_path
        self.participants = []
        self.utterances = []

        # General chat attributes
        self.color_words = ''
        self.comment = ''
        self.date = ''
        self.font = ''
        self.languages = []
        self.pid = ''
        self.situation = ''
        self.time_duration = ''

        # Line to starts with {'*', '@', '%'}
        with open(self.chat_path) as fd:
            contents = re.sub(r'\n\t', ' ', fd.read(), re.MULTILINE)
        for line in contents.split('\n'):
            if not line:
                continue
            start_char = line[0]
            if start_char == '@':
                self.set_attribute(line)
            elif start_char == '*':
                self.utterances.append(Utterance(line))
            elif start_char == '%':
                self.utterances[-1].comments.append(UtteranceComment(line))

        self.corpus = self.participants[0].corpus

        self._validate()

    def _validate(self):
        assert self.comment or self.situation, '%s: Comment or situation is required' % self.chat_path
        assert self.date, '%s: date is required' % self.chat_path
        assert self.languages, '%s: languages is required' % self.chat_path
        assert self.participants, '%s: participants is required' % self.chat_path
        assert self.pid, '%s: pid is required' % self.chat_path
        assert self.id, '%s: id is required' % self.chat_path
        assert self.corpus, '%s: corpus is required' % self.chat_path

    def _set_participant_meta(self, meta_string):
        meta_list = meta_string.split('|')
        id = meta_list[2]
        for p in self.participants:
            if p.id == id:
                return p.set_meta(meta_list)

    def set_attribute(self, attribute_line):
        if self._ignore_patt.match(attribute_line):
            return
        attribute_name, attribute_value = attribute_line.split(':', maxsplit=1)

        attribute_name = attribute_name.lstrip('@').rstrip(':').replace(' ', '_')
        attribute_value = attribute_value.strip()

        if attribute_name not in self.VALID_ATTRIBUTES:
            raise ValueError('Invalid chat attribute: %r' % attribute_line)

        if attribute_name == 'Languages':
            self.languages = attribute_value.split(' , ')
        elif attribute_name == 'Participants':
            for p in attribute_value.split(' , '):
                participant = Participant(*p.split())
                self.participants.append(participant)
        elif attribute_name == 'ID':
            self._set_participant_meta(attribute_value)
        elif attribute_name == 'Date':
            t = time.strptime(attribute_value, "%d-%b-%Y")
            self.date = datetime(*t[:6]).strftime("%Y-%m-%d")
        else:
            setattr(self, attribute_name.lower(), attribute_value)

    def __str__(self):
        attributes = self.CHAT_ATTRIBUTES + self._OTHER_ATTRIBUTES
        values = [(attribute, getattr(self, attribute.lower())) for attribute in attributes]
        return '\n'.join('%s: %s' % t for t in values)

    def create_xml(self):
        xml = TEMPLATE.render(chat=self)
        return '\n'.join((line for line in xml.split('\n') if line.split()))

    @classmethod
    def read_chats(cls, chats_dir):
        if not os.path.isdir(chats_dir):
            raise ValueError('Invalid chat directory: %s' % chats_dir)
        chats = []
        for root, _, files in os.walk(chats_dir):
            for f in files:
                if f.endswith('.cha'):
                    chats.append(Chat(os.path.join(root, f)))
        return chats


chats = Chat.read_chats('./cha_transcripts/Vija')
c = chats[-1]
print(c)
print('-'*50)
print(c.create_xml())
print(c.chat_path)
# import ipdb
# ipdb.set_trace()
