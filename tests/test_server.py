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
from unittest.mock import Mock

import pytest
from lsprotocol import types
from pygls.workspace import Document, Workspace

from anakinls import server as aserver


class Server:
    jediEnvironment = None
    jediProject = None

    def __init__(self):
        super().__init__()
        self.workspace = Workspace('', None)


@pytest.fixture()
def server():
    return Server()


def test_completion(server):
    uri = 'file://test_completion.py'
    content = """
def foo(a, *, b, c=None):
    pass

foo"""
    doc = Document(uri, content)
    server.workspace.get_text_document = Mock(return_value=doc)
    aserver.completionFunction = aserver._completions_snippets
    completion = aserver.completions(
        server,
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=4, character=3),
            context=types.CompletionContext(
                trigger_kind=types.CompletionTriggerKind.Invoked
            ),
        ),
    )
    assert len(completion.items) == 2
    item = completion.items[0]
    assert item.insert_text is None
    assert item.label == 'foo'
    assert item.sort_text == 'aaafoo'
    assert item.insert_text_format is None
    item = completion.items[1]
    assert item.label == 'foo(a, b)'
    assert item.sort_text == 'aazfoo'
    assert item.insert_text_format == types.InsertTextFormat.Snippet
    assert item.insert_text == 'foo(${1:a}, b=${2:b})$0'


def test_hover(server):
    uri = 'file://test_hover.py'
    content = '''
def foo(a, *, b, c=None):
    """docstring"""
    pass

foo'''
    doc = Document(uri, content)
    server.workspace.get_text_document = Mock(return_value=doc)
    aserver.hoverFunction = aserver._docstring
    h = aserver.hover(
        server,
        types.TextDocumentPositionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=5, character=0),
        ),
    )
    assert h is not None
    assert isinstance(h.contents, types.MarkupContent)
    assert h.contents.kind == types.MarkupKind.PlainText
    assert h.contents.value == 'foo(a, *, b, c=None)\n\ndocstring'


def test_diff_to_edits():
    diff = """--- /path/to/original	timestamp
+++ /path/to/new	timestamp
@@ -1,3 +1,9 @@
+This is an important
+notice! It should
+therefore be located at
+the beginning of this
+document!
+
 This part of the
 document has stayed the
 same from version to
@@ -8,13 +14,8 @@
 compress the size of the
 changes.

-This paragraph contains
-text that is outdated.
-It will be deleted in the
-near future.
-
 It is important to spell
-check this dokument. On
+check this document. On
 the other hand, a
 misspelled word isn't
 the end of the world.
@@ -22,3 +23,7 @@
 this paragraph needs to
 be changed. Things can
 be added after it.
+
+This paragraph contains
+important new additions
+to this document.
"""
    edits = aserver._get_text_edits(diff)
    assert len(edits) == 4
    assert str(edits[0].range) == '0:0-0:0'
    assert str(edits[1].range) == '10:0-15:0'
    assert edits[1].new_text == ''
    assert str(edits[2].range) == '16:0-17:0'
    assert edits[2].new_text == 'check this document. On\n'
    assert str(edits[3].range) == '24:0-24:0'


def test_no_pyflakes_syntax_error_diagnostic(server):
    uri = 'file://test_diagnostic.py'
    content = 'pass\n\nif\n'
    doc = Document(uri, content)
    server.workspace.get_text_document = Mock(return_value=doc)
    server.publish_diagnostics = Mock()
    aserver._validate(server, uri)
    assert server.publish_diagnostics.called
    diagnostics = server.publish_diagnostics.call_args[0][1]
    assert len(diagnostics) == 1
    assert diagnostics[0].source == 'jedi'
