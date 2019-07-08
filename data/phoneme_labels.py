from string import punctuation, printable

punctuation = punctuation.replace('-','')

class PhonemeLabels:
    def __init__(self,
                 phoneme_map,
                 phoneme_separator='-', # for readability, phonemes are kept as is
                 space_token = ' ',
                 blank_token = '_'
                ):
        self.phoneme_separator = phoneme_separator
        self.phoneme_map = phoneme_map
        self.inverse_map = {v: k for k, v in phoneme_map.items()}
        self.space_token_id = self.phoneme_map[space_token]
        assert self.phoneme_map[blank_token] == 0

    def parse(self, text):
        text = ''.join([_ for _ in list(text) if _ not in punctuation and _ in printable])
        # this assumesa
        # (i)  text is normalized
        # (ii) symbols not present in map are omitted
        phonetic_transcript = []
        words = text.split(' ')
        for word in words:
            split_word = word.split(self.phoneme_separator)
            word_transcript = []
            for c in split_word:
                if c in self.phoneme_map:
                    code = self.phoneme_map[c]
                if len(word_transcript)>1 and word_transcript[-1] == code:
                    code = self.phoneme_map['2']
                word_transcript.append(code)
            phonetic_transcript.append(word_transcript+[self.space_token_id])
        return list(itertools.chain(*phonetic_transcript))[:-1] #  remove last space token

    def render_transcript(self, codes):
        return ''.join([self.inverse_map[i] for i in codes])