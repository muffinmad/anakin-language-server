# Copyright (C) 2020  Andrii Kolomoiets <andreyk.mad@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pytest

from unittest.mock import Mock

from anakinls import server as aserver

from pygls import types
from pygls.workspace import Document, Workspace


class Server():
    jediEnvironment = None
    jediProject = None

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
    aserver.completionFunction = aserver._completions_snippets
    completion = aserver.completions(
        server,
        types.CompletionParams(
            types.TextDocumentIdentifier(uri),
            types.Position(4, 3),
            types.CompletionContext(types.CompletionTriggerKind.Invoked)
        ))
    assert len(completion.items) == 2
    item = completion.items[0]
    assert item.insertText is None
    assert item.label == 'foo'
    assert item.sortText == 'aaafoo'
    assert item.insertTextFormat is None
    item = completion.items[1]
    assert item.label == 'foo(a, b)'
    assert item.sortText == 'aazfoo'
    assert item.insertTextFormat == types.InsertTextFormat.Snippet
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
    aserver.hoverFunction = aserver._docstring
    h = aserver.hover(server, types.TextDocumentPositionParams(
        doc,
        types.Position(5, 0)))
    assert h is not None
    assert isinstance(h.contents, types.MarkupContent)
    assert h.contents.kind == types.MarkupKind.PlainText
    assert h.contents.value == 'foo(a, *, b, c=None)\n\ndocstring'
