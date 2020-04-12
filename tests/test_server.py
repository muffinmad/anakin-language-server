import pytest

from unittest.mock import Mock

from anakinls.server import completions

from pygls.types import (CompletionParams, TextDocumentIdentifier,
                         Position, CompletionContext, CompletionTriggerKind,
                         InsertTextFormat)
from pygls.workspace import Document, Workspace


class Server():
    jediEnvironment = None

    def __init__(self):
        super().__init__()
        self.workspace = Workspace('', None)


server = Server()


def test_completion():
    uri = 'file://test.py'
    content = '''
def foo(a, *, b, c=None):
    pass

foo'''
    doc = Document(uri, content)
    server.workspace.get_document = Mock(return_value=doc)
    completion = completions(
        server,
        CompletionParams(
            TextDocumentIdentifier(uri),
            Position(4, 3),
            CompletionContext(CompletionTriggerKind.Invoked)
        ))
    assert len(completion.items) == 2
    item = completion.items[0]
    assert item.insertText is None
    assert item.label == 'foo'
    assert item.insertTextFormat is None
    item = completion.items[1]
    assert item.label == 'foo(a, b)'
    assert item.insertTextFormat == InsertTextFormat.Snippet
    assert item.insertText == 'foo(${1:a}, b=${2:b})$0'
