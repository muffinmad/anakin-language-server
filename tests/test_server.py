import pytest

from unittest.mock import Mock

from anakinls.server import completions, hover

from pygls.types import (CompletionParams, TextDocumentIdentifier,
                         Position, CompletionContext, CompletionTriggerKind,
                         InsertTextFormat, TextDocumentPositionParams, MarkupContent,
                         MarkupKind)
from pygls.workspace import Document, Workspace


class Server():
    jediEnvironment = None

    def __init__(self):
        super().__init__()
        self.workspace = Workspace('', None)


server = Server()


def test_completion():
    uri = 'file://test_completion.py'
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


def test_hover():
    uri = 'file://test_hover.py'
    content = '''
def foo(a, *, b, c=None):
    """docstring"""
    pass

foo'''
    doc = Document(uri, content)
    server.workspace.get_document = Mock(return_value=doc)
    h = hover(server, TextDocumentPositionParams(doc, Position(5, 0)))
    assert h is not None
    assert isinstance(h.contents, MarkupContent)
    assert h.contents.kind == MarkupKind.PlainText
    assert h.contents.value == 'docstring'


def test_hover_no_docstring():
    uri = 'file://test_hover_no_docstring.py'
    content = '''
def foo(a, *, b, c=None):
    pass

foo'''
    doc = Document(uri, content)
    server.workspace.get_document = Mock(return_value=doc)
    h = hover(server, TextDocumentPositionParams(doc, Position(4, 0)))
    assert h is not None
    assert isinstance(h.contents, MarkupContent)
    assert h.contents.kind == MarkupKind.PlainText
    assert h.contents.value == 'foo(a, *, b, c=None)'
