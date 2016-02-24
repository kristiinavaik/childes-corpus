import os
import re
import time
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

TEMPLATE_ENV = Environment(loader=FileSystemLoader('.'))
TEMPLATE = TEMPLATE_ENV.get_template('template.xml')


class Event(object):

    MAPPING = {
        '[!!]':  'Contrastive Stressing',
        '[!]':   'Stressing',
        '[%':    'Comment on Main Line',
        '[*]':   'Error Marking',
        '[+':    'Postcodes',
        '[///]': 'Reformulation',
        '[//]':  'Retracing',
        '[/]':   'Repetition',
        '[:':    'Replacement',
        '[<]':   'Overlap Precedes',
        '[=!':   'Paralinguistic Material',
        '[=':    'Explanation',
        '[=?':   'Alternative Transcription',
        '[>]':   'Overlap Follows',
        '[?]':   'Best Guess',
        '[^':    'Complex Local Event',
        '[x':    'Multiple Repetition'
    }

    def __init__(self, pattern):
        self.pattern = pattern


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


class Utterance(object):

    def __init__(self, line, comment=''):
        self._line = line
        self.comment = comment

    def extend_line(self, extend_line):
        self._line = '%s %s' % (self._line, extend_line.strip())

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
                self.utterances[-1].comment = line

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
import ipdb
ipdb.set_trace()
