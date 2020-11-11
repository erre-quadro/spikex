from spacy.tokens import Doc, Span, Token

from .matcher import Matcher


class Labeler:
    def __init__(self, vocab, validate=None):
        self._matcher = Matcher(vocab, validate)
        Token.set_extension("labels", default=[], force=True)
        Doc.set_extension("labelings", default=[], force=True)

    def add(self, label, patterns, on_match=None):
        """
        Add a labeling-rules to the labeler.
        
        Parameters
        ----------
        label: str
            The label related to patterns.
        patterns: list
            The pattern matching rules.
        on_match: callable, optional
            Callback executed on match, by default None.
        """
        self._matcher.add(label, patterns, on_match=on_match)

    def __call__(self, doc: Doc):
        """
        Collect all labels related to patterns matching tokens.
        Each token have a `labels` extension in which to store them.
        The supplied `Doc` have a `labelings` extension in which 
        all labeled spans are collected. 

        Parameters
        ----------
        doc: Doc
            The doc to label over.

        Returns
        -------
        Doc
            The doc after labeling.
        """
        for key, start, end in self._matcher(doc):
            label = doc.vocab.strings[key]
            span = Span(doc, start, end, label)
            for token in span:
                if label in token._.labels:
                    continue
                token._.labels.append(label)
            doc._.labelings.append(span)
        return doc
