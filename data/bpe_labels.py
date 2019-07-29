import re
import json
import string
import pandas as pd
import sentencepiece as sp
from string import punctuation, printable

punctuation = punctuation.replace('-','')
printable = printable.replace('\n','')

with open('../phonemes_ru.json') as json_file:
    ru_phonemes = json.load(json_file)

# a hack to use BPE with phonemes
# you cannot just apply sp because phonemes have 2-3 letter codes
fake_alphabet = string.ascii_letters + \
                'АаБбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя'
phoneme_2_fake = {phoneme : fake_alphabet[i]
                  for i, phoneme in enumerate(ru_phonemes)}
fake_2_phoneme = {v: k for k, v in phoneme_2_fake.items()}


def remove_extra_spaces(text):
    return re.sub(' +', ' ', text)


class Labels:
    def __init__(self,
                 use_phonemes=False,
                 sp_model='../spm_train_v05_cleaned_asr_10s_phoneme.model',
                 sp_model_phoneme='../phoneme_spm_train_v05_cleaned_asr_10s_phoneme.model',
                 sp_space_token='▁'):

        self.use_phonemes = use_phonemes
        # will not be used 
        # if sp is trained with coverage of 1.0
        # and default params
        self.remove_sp_tokens = ['<unk>', '<s>', '</s>']
        self.sp_space_token = sp_space_token

        self.spm = sp.SentencePieceProcessor()
        if self.use_phonemes:
            self.spm.Load(sp_model_phoneme)
        else:   
            self.spm.Load(sp_model)
        sp_tokens = self.spm.get_piece_size()
        print('Sentencepiece model loaded, {} tokens'.format(sp_tokens))

        pieces = pd.DataFrame([{'piece_id': i,
                                'piece_str': self.spm .IdToPiece(id=i),
                                'piece_score': self.spm .GetScore(id=i)} 
                               for i in range(0,sp_tokens)])
        pieces = pieces[~pieces.piece_str.isin(self.remove_sp_tokens+[self.sp_space_token])]

        # reserve 0 for CTC blank
        self.labels_map = {"_" : 0}
        for key in list(pieces.piece_str.values):
            self.labels_map[key] = len(self.labels_map)
        self.labels_map['2'] = len(self.labels_map)
        self.labels_map[' '] = len(self.labels_map)
        self.labels_map_reverse = {v: k for k, v in self.labels_map.items()}

    def encode_phonemes(text):
        text = text.replace('\n','')
        out = []
        words = text.split(' ')
        for i, word in enumerate(words):
            phonemes = word.split('-')
            for phoneme in phonemes:
                if phoneme in phoneme_2_fake:
                    out.append(phoneme_2_fake[phoneme])
                else:
                    print(phoneme, text)
                    raise ValueError('Phoneme not in dict')
            if i < len(words)-1:
                out.append(' ')
        return ''.join(out)


    def parse(self, text):

        text = ''.join([_ for _ in list(text)
                        if _ not in punctuation and _ in printable])
        text = remove_extra_spaces(text).strip()
        if not self.use_phonemes:
            text = text.lower()
        # print(text)

        transcript = []

        if self.use_phonemes:

            # to fake alphabet
            fake_encoded = encode_phonemes(text)
            sp_transcript = self.spm.encode_as_pieces(fake_encoded)

            out = []
            for word in sp_transcript:
                if word == self.sp_space_token:
                    out.append(' ')
                else:
                    for char in word:
                        out.append(fake_2_phoneme[char])
            try:
                # convert back and check
                assert str(text.replace('-','')).strip() == str(''.join(out)).strip()
            except Exception as e:
                print('Error {} with {}'.format(str(e),
                                                text))         

        else:
            sp_transcript = self.spm.encode_as_pieces(text)
     
        # print(sp_transcript)

        for i, token in enumerate(sp_transcript):
            if token in self.remove_sp_tokens:
                pass
            elif token == self.sp_space_token:
                # replace spm space token with our space
                code = self.labels_map[' ']
            else:
                code = self.labels_map[token]
                if transcript and transcript[-1] == code:
                    code = self.labels_map['2']  # double char
            transcript.append(code)

        return transcript

    def render_transcript(self, codes):
        if self.use_phonemes:
            raise NotImplementedError('This method is not applicable for phoneme BPE')
        else:
            return ''.join([self.labels_map_reverse[i] for i in codes])