import regex as re


class Fragment:
    """
    A fragment of text that ends with a possible sentence boundary
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self.next = None
        self.label = None
        self.features = None
        self.prediction = None
        self.is_sent_end = False

    def __str__(self):
        s = "".join([t.text_with_ws for t in self.tokens])
        if self.is_sent_end:
            s += " <EOS> "
        return s

    @property
    def first_token(self):
        if not self.tokens:
            return
        return self.tokens[0]

    @property
    def last_token(self):
        if not self.tokens:
            return
        return self.tokens[-1]

    def words(self, clean=None):
        return [
            _clean(token.text) if clean is not None else token.text
            for token in self.tokens
        ]


def _clean(text):
    # normalize numbers, discard some punctuation that can be ambiguous
    t = re.sub(r"[.,\d]*\d", "<NUM>", text)
    t = re.sub(r"[^a-zA-Z0-9,.;:<>\-'\/?!$% ]", "", t)
    t = t.replace("--", " ")  # sometimes starts a sentence... trouble
    return t
