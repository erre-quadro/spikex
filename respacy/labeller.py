from spacy.tokens import Doc, Token

from .matcher import REMatcher


class Labeller:
    def __init__(self, validate: bool = None):

        self._matcher = REMatcher(validate)
        Token.set_extension("labels", default=[], force=True)

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
        Label all tokens matching the supplied patterns
        by using the token extension `labels`, in which
        are collected as a set of uniqueness.

        Parameters
        ----------
        doc: Doc
            The document to label over.

        Returns
        -------
        list
            A list of `(label, i, start, end)` tuples,
            describing the matches labelled. A tuple describes a span
            `doc[start:end]` matched by the *i-th* pattern of the *label*.
        """
        matches = self._matcher(doc)
        for key, start, end in matches:
            label = doc.vocab.strings[key]
            for token in doc[start:end]:
                if label in token._.labels:
                    continue
                token._.labels.append(label)
        return matches

    @staticmethod
    def from_labellings(labellings, on_match=None, validate=None):
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
        labeller = Labeller(validate)
        for labelling in labellings:
            label = labelling["label"]
            pattern = labelling["pattern"]
            labeller.add(label, [pattern], on_match=on_match)
        return labeller
