from spacy.tokens import Doc, Span, Token

from .matcher import Matcher


class Labeller:
    def __init__(self, vocab, validate: bool = None):
        Doc.set_extension("labellings", default=[], force=True)
        Token.set_extension("labels", default=[], force=True)

        self._matcher = Matcher(vocab, validate)

    def add(self, label, patterns, on_match=None):
        """
        Add a labelling-rule to the labeller.
        
        Parameters
        ----------
        label: str
            The label to assign to tokens whether a pattern matches.
        patterns: list
            The patterns to add for the given label.
        on_match: callable, optional
            Callback executed on match, by default None.
        """
        self._matcher.add(label, patterns, on_match=on_match)

    def __call__(self, doc: Doc):
        """
        Collect all token labels whether it matches in patterns.
        Each token will have them in its `labels` extension.
        The supplied `Doc` will have a `labellings` extension in
        which all labelling-spans are collected. 


        Parameters
        ----------
        doc: Doc
            The document to label over.

        Returns
        -------
        Doc
            The doc after being labelled.
        """
        matches = self._matcher(doc, best_sort=True)
        for key, start, end in matches:
            label = doc.vocab.strings[key]
            span = Span(doc, start, end, label)
            for token in span:
                if label in token._.labels:
                    continue
                token._.labels.append(label)
            doc._.labellings.append(span)
        return doc

    @staticmethod
    def from_labellings(labellings, vocab, *, on_match=None, validate=None):
        """
        Create a `Labeller` instance containing labelling-rules.
        A labelling-rule consists of:
            a label,
            a pattern.
        
        Parameters
        ----------
        labellings: list
            A list of *labellings*.
        on_match: callable, optional
            Callback executed on match, by default None.
        validate: bool, optional
            Whether to perform a patterns validation, by default None.
        
        Returns
        -------
        Labeller
            Instance of a `Labeller`.
        """
        labeller = Labeller(vocab, validate)
        for labelling in labellings:
            label = labelling["label"]
            pattern = labelling["pattern"]
            labeller.add(label, [pattern], on_match=on_match)
        return labeller
