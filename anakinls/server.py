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

import logging
import re

from difflib import Differ
from inspect import Parameter
from typing import List, Dict, Optional, Any, Iterator, Callable, Union

from jedi import (Script, create_environment,  # type: ignore
                  get_default_environment,
                  settings as jedi_settings, get_default_project,
                  RefactoringError)
from jedi.api.classes import Name, Completion  # type: ignore
from jedi.api.refactoring import Refactoring  # type: ignore

from pycodestyle import (BaseReport as CodestyleBaseReport,  # type: ignore
                         Checker as CodestyleChecker,
                         StyleGuide as CodestyleStyleGuide)

from pyflakes.api import check as pyflakes_check  # type: ignore

from yapf.yapflib.yapf_api import FormatCode  # type: ignore

from pygls.lsp.methods import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
                               TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,
                               HOVER, SIGNATURE_HELP, DEFINITION,
                               REFERENCES, WORKSPACE_DID_CHANGE_CONFIGURATION,
                               TEXT_DOCUMENT_WILL_SAVE, TEXT_DOCUMENT_DID_SAVE,
                               DOCUMENT_SYMBOL, CODE_ACTION, FORMATTING,
                               RANGE_FORMATTING, RENAME, DOCUMENT_HIGHLIGHT)
from pygls.lsp import types
from pygls.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.uris import to_fs_path

from .version import get_version  # type: ignore

RE_WORD = re.compile(r'\w*')


_COMPLETION_TYPES = {
    'module': types.CompletionItemKind.Module,
    'class': types.CompletionItemKind.Class,
    'instance': types.CompletionItemKind.Reference,
    'function': types.CompletionItemKind.Function,
    'param': types.CompletionItemKind.Variable,
    'keyword': types.CompletionItemKind.Keyword,
    'statement': types.CompletionItemKind.Variable,
    'property': types.CompletionItemKind.Property
}


completionFunction: Callable[[List[Completion], types.Range],
                             Iterator[types.CompletionItem]]
documentSymbolFunction: Union[
    Callable[[str, List[str], List[Name]], List[types.DocumentSymbol]],
    Callable[[str, List[str], List[Name]], List[types.SymbolInformation]]]

hoverMarkup: types.MarkupKind = types.MarkupKind.PlainText
hoverFunction: Callable[[Name], str]


class AnakinLanguageServerProtocol(LanguageServerProtocol):

    def bf_initialize(
            self, params: types.InitializeParams) -> types.InitializeResult:
        result = super().bf_initialize(params)
        global jediEnvironment
        global jediProject
        global completionFunction
        global documentSymbolFunction
        global hoverMarkup
        global hoverFunction
        if params.initialization_options:
            venv = params.initialization_options.get('venv', None)
        else:
            venv = None
        if venv:
            jediEnvironment = create_environment(venv, safe=False)
        else:
            jediEnvironment = get_default_environment()
        jediProject = get_default_project(getattr(params, 'rootPath', None))
        logging.info(f'Jedi environment python: {jediEnvironment.executable}')
        logging.info('Jedi environment sys_path:')
        for p in jediEnvironment.get_sys_path():
            logging.info(f'  {p}')
        logging.info(f'Jedi project path: {jediProject._path}')

        def get_attr(o, *attrs):
            try:
                for attr in attrs:
                    o = getattr(o, attr)
                return o
            except AttributeError:
                return None

        caps = getattr(params.capabilities, 'text_document', None)

        if get_attr(caps, 'completion', 'completion_item', 'snippet_support'):
            completionFunction = _completions_snippets
        else:
            completionFunction = _completions

        if get_attr(caps,
                    'document_symbol', 'hierarchical_document_symbol_support'):
            documentSymbolFunction = _document_symbol_hierarchy
        else:
            documentSymbolFunction = _document_symbol_plain

        hover = get_attr(caps, 'hover', 'content_format')
        if hover:
            hoverMarkup = hover[0]
        if hoverMarkup == types.MarkupKind.Markdown:
            hoverFunction = _docstring_markdown
        else:
            hoverFunction = _docstring

        # pygls does not currently support serverInfo of LSP v3.15
        result.server_info = types.ServerInfo(
            name='anakinls',
            version=get_version(),
        )
        return result


server = LanguageServer(protocol_cls=AnakinLanguageServerProtocol)

scripts: Dict[str, Script] = {}
pycodestyleOptions: Dict[str, Any] = {}
mypyConfigs: Dict[str, str] = {}

jediEnvironment = None
jediProject = None

completionPrefixPlain = 'a'
completionPrefixSnippet = 'z'

jediHoverFunction = Script.help

config = {
    'pyflakes_errors': [
        'UndefinedName'
    ],
    'pycodestyle_config': None,
    'help_on_hover': True,
    'mypy_enabled': False,
    'completion_snippet_first': False,
    'completion_fuzzy': False,
    'diagnostic_on_open': True,
    'diagnostic_on_save': True,
    'diagnostic_on_change': False,
    'yapf_style_config': 'pep8'
}

differ = Differ()


def get_script(ls: LanguageServer, uri: str, update: bool = False) -> Script:
    result = None if update else scripts.get(uri)
    if not result:
        document = ls.workspace.get_document(uri)
        result = Script(
            code=document.source,
            path=document.path,
            environment=jediEnvironment,
            project=jediProject
        )
        scripts[uri] = result
    return result


class PyflakesReporter:

    def __init__(self, result, script, errors):
        self.result = result
        self.script = script
        self.errors = errors

    def unexpectedError(self, _filename, msg):
        self.result.append(types.Diagnostic(
            range=types.Range(start=types.Position(line=0, character=0),
                              end=types.Position(line=0, character=0)),
            message=msg,
            severity=types.DiagnosticSeverity.Error,
            source='pyflakes'
        ))

    def _get_codeline(self, line):
        return self.script._code_lines[line].rstrip('\n\r')

    def syntaxError(self, _filename, msg, lineno, offset, _text):
        line = lineno - 1
        col = offset or 0
        self.result.append(types.Diagnostic(
            range=types.Range(
                start=types.Position(line=line, character=col),
                end=types.Position(
                    line=line,
                    character=len(self._get_codeline(line)) - col)),
            message=msg,
            severity=types.DiagnosticSeverity.Error,
            source='pyflakes'
        ))

    def flake(self, message):
        line = message.lineno - 1
        if message.__class__.__name__ in self.errors:
            severity = types.DiagnosticSeverity.Error
        else:
            severity = types.DiagnosticSeverity.Warning
        self.result.append(types.Diagnostic(
            range=types.Range(
                start=types.Position(line=line, character=message.col),
                end=types.Position(line=line,
                                   character=len(self._get_codeline(line)))),
            message=message.message % message.message_args,
            severity=severity,
            source='pyflakes'
        ))


class CodestyleReport(CodestyleBaseReport):

    def __init__(self, options, result):
        super().__init__(options)
        self.result = result

    def error(self, line_number, offset, text, check):
        code = text[:4]
        if self._ignore_code(code) or code in self.expected:
            return
        line = line_number - 1
        self.result.append(types.Diagnostic(
            range=types.Range(
                start=types.Position(line=line, character=offset),
                end=types.Position(
                    line=line,
                    character=len(self.lines[line].rstrip('\n\r')))
            ),
            message=text,
            severity=types.DiagnosticSeverity.Warning,
            code=code,
            source='pycodestyle'
        ))


def _get_workspace_folder_path(ls: LanguageServer, uri: str) -> str:
    # find workspace folder uri belongs to
    folders = sorted(
        (f.uri
         for f in ls.workspace.folders.values()
         if uri.startswith(f.uri)),
        key=len, reverse=True
    )
    if folders:
        return to_fs_path(folders[0])
    return ls.workspace.root_path


def get_pycodestyle_options(ls: LanguageServer, uri: str):
    folder = _get_workspace_folder_path(ls, uri)
    result = pycodestyleOptions.get(folder)
    if not result:
        kwargs = {'config_file': config['pycodestyle_config']}
        if folder:
            kwargs['paths'] = [folder]
        result = CodestyleStyleGuide(**kwargs).options
        pycodestyleOptions[folder] = result
    return result


def get_mypy_config(ls: LanguageServer, uri: str) -> Optional[str]:
    folder = _get_workspace_folder_path(ls, uri)
    if folder in mypyConfigs:
        return mypyConfigs[folder]
    import os
    from mypy.defaults import CONFIG_FILES
    result = ''
    for filename in CONFIG_FILES:
        filename = os.path.expanduser(filename)
        if not os.path.isabs(filename):
            filename = os.path.join(folder, filename)
        if os.path.exists(filename):
            result = filename
            break
    mypyConfigs[folder] = result
    return result


def _mypy_check(ls: LanguageServer, uri: str, script: Script,
                result: List[types.Diagnostic]):
    from mypy import api
    assert jediEnvironment is not None
    version_info = jediEnvironment.version_info
    if config['diagnostic_on_change']:
        args = ['--command', script._code]
    else:
        args = [to_fs_path(uri)]
    lines = api.run([
        '--python-executable', jediEnvironment.executable,
        '--python-version', f'{version_info.major}.{version_info.minor}',
        '--config-file', get_mypy_config(ls, uri),
        '--hide-error-context',
        '--show-column-numbers',
        '--show-error-codes',
        '--no-pretty',
        '--no-error-summary'
    ] + args)
    if lines[1]:
        ls.show_message(lines[1], types.MessageType.Error)
        return

    for line in lines[0].split('\n'):
        parts = line.split(':', 4)
        if len(parts) < 5:
            continue
        _fn, row, column, err_type, message = parts
        row = int(row) - 1
        column = int(column) - 1
        if err_type.strip() == 'note':
            severity = types.DiagnosticSeverity.Hint
        else:
            severity = types.DiagnosticSeverity.Warning
        result.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(line=row, character=column),
                    end=types.Position(
                        line=row,
                        character=len(script._code_lines[row]))),
                message=message.strip(),
                severity=severity,
                source='mypy'
            )
        )
    return result


def _validate(ls: LanguageServer, uri: str, script: Script = None):
    if script is None:
        script = get_script(ls, uri)

    # Jedi
    result = [
        types.Diagnostic(
            range=types.Range(
                start=types.Position(line=x.line - 1,
                                     character=x.column),
                end=types.Position(line=x.until_line - 1,
                                   character=x.until_column)
            ),
            message=x.get_message(),
            severity=types.DiagnosticSeverity.Error,
            source='jedi'
        )
        for x in script.get_syntax_errors()
    ]
    if result:
        ls.publish_diagnostics(uri, result)
        return

    # pyflakes
    pyflakes_check(script._code, script.path,
                   PyflakesReporter(result, script, config['pyflakes_errors']))

    # pycodestyle
    codestyleopts = get_pycodestyle_options(ls, uri)
    CodestyleChecker(
        script.path, script._code.splitlines(True), codestyleopts,
        CodestyleReport(codestyleopts, result)
    ).check_all()

    # mypy
    if config['mypy_enabled']:
        try:
            _mypy_check(ls, uri, script, result)
        except Exception as e:
            ls.show_message(f'mypy check error: {e}',
                            types.MessageType.Warning)

    ls.publish_diagnostics(uri, result)


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams):
    if config['diagnostic_on_open']:
        _validate(ls, params.text_document.uri)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: LanguageServer, params: types.DidCloseTextDocumentParams):
    try:
        del scripts[params.text_document.uri]
    except KeyError:
        pass


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams):
    script = get_script(ls, params.text_document.uri, True)
    if config['diagnostic_on_change']:
        _validate(ls, params.text_document.uri, script)


def _completion_sort_key(completion: Completion, prefix: str = '') -> str:
    name = completion.name
    if name.startswith('__'):
        return f'zz{prefix}{name}'
    if name.startswith('_'):
        return f'za{prefix}{name}'
    return f'aa{prefix}{name}'


def _completion_item(completion: Completion, r: types.Range) -> Dict:
    label = completion.name
    _r = r
    lnm = completion._like_name_length
    if lnm == 1 and label[0] in {'"', "'"}:
        lnm = 0
        label = label[1:]
    elif lnm:
        _r = types.Range(
            start=types.Position(line=r.start.line,
                                 character=r.start.character - lnm),
            end=r.end)
    return dict(
        label=label,
        kind=_COMPLETION_TYPES.get(completion.type,
                                   types.CompletionItemKind.Text),
        documentation=completion.docstring(raw=True),
        text_edit=types.TextEdit(range=_r, new_text=label)
    )


def _completions(completions: List[Completion],
                 r: types.Range) -> Iterator[types.CompletionItem]:
    return (
        types.CompletionItem(
            sort_text=_completion_sort_key(completion),
            **_completion_item(completion, r),
        ) for completion in completions
    )


def _completions_snippets(completions: List[Completion],
                          r: types.Range) -> Iterator[types.CompletionItem]:
    for completion in completions:
        item = _completion_item(completion, r)
        yield types.CompletionItem(
            sort_text=_completion_sort_key(completion, completionPrefixPlain),
            **item
        )
        if completion.type == 'property':
            continue
        for signature in completion.get_signatures():
            names = []
            snippets = []
            for i, param in enumerate(signature.params):
                if param.kind == Parameter.VAR_KEYWORD:
                    break
                if '=' in param.description:
                    break
                if param.name == '/':
                    continue
                names.append(param.name)
                if param.kind == Parameter.KEYWORD_ONLY:
                    snippet_prefix = f'{param.name}='
                else:
                    snippet_prefix = ''
                snippets.append(
                    f'{snippet_prefix}${{{i + 1}:{param.name}}}'
                )
            names_str = ', '.join(names)
            snippets_str = ', '.join(snippets)
            yield types.CompletionItem(**dict(
                item,
                sort_text=_completion_sort_key(completion,
                                               completionPrefixSnippet),
                label=f'{completion.name}({names_str})',
                insert_text=f'{completion.name}({snippets_str})$0',
                insert_text_format=types.InsertTextFormat.Snippet,
                text_edit=None
            ))


@server.feature(COMPLETION, types.CompletionOptions(trigger_characters=['.']))
def completions(ls: LanguageServer, params: types.CompletionParams):
    global completionFunction
    script = get_script(ls, params.text_document.uri)
    completions = script.complete(
        params.position.line + 1,
        params.position.character,
        fuzzy=config['completion_fuzzy']
    )
    code_line = script._code_lines[params.position.line]
    word_match = RE_WORD.match(code_line[params.position.character:])
    if word_match:
        word_rest = word_match.end()
    else:
        word_rest = 0
    r = types.Range(
        start=types.Position(line=params.position.line,
                             character=params.position.character),
        end=types.Position(line=params.position.line,
                           character=params.position.character + word_rest)
    )
    return types.CompletionList(is_incomplete=False,
                                items=list(completionFunction(completions, r)))


def _docstring(name: Name) -> str:
    return name.docstring()


def _docstring_markdown(name: Name) -> str:
    doc = name.docstring()
    if not doc:
        return ''
    if name.type in ['class', 'function']:
        try:
            sig, doc = doc.split('\n\n', 1)
        except ValueError:
            sig = doc
            doc = False
        sig = f'```python\n{sig}\n```'
        if doc:
            return f'{sig}\n\n```\n{doc}\n```'
        return sig
    return f'```\n{doc}\n```'


@server.feature(HOVER)
def hover(ls: LanguageServer,
          params: types.TextDocumentPositionParams) -> Optional[types.Hover]:
    global hoverFunction
    global jediHoverFunction
    script = get_script(ls, params.text_document.uri)
    names = jediHoverFunction(script,
                              params.position.line + 1,
                              params.position.character)
    result = '\n\n'.join(map(hoverFunction, names))
    if result:
        return types.Hover(
            contents=types.MarkupContent(kind=hoverMarkup, value=result)
        )
    return None


@server.feature(SIGNATURE_HELP,
                types.SignatureHelpOptions(trigger_characters=['(', ',']))
def signature_help(
        ls: LanguageServer,
        params: types.TextDocumentPositionParams
) -> Optional[types.SignatureHelp]:
    script = get_script(ls, params.text_document.uri)
    signatures = script.get_signatures(params.position.line + 1,
                                       params.position.character)

    result = []
    idx = -1
    param_idx = -1
    i = 0
    for signature in signatures:
        if signature.index is None:
            continue
        result.append(types.SignatureInformation(
            label=signature.to_string(),
            parameters=[
                types.ParameterInformation(label=param.name)
                for param in signature.params
            ]
        ))
        if signature.index > param_idx:
            param_idx = signature.index
            idx = i
        i += 1
    if result:
        return types.SignatureHelp(
            signatures=[result[idx]],
            active_signature=0,
            active_parameter=param_idx)
    return None


def _get_name_range(name: Name) -> types.Range:
    return types.Range(
        start=types.Position(line=name.line - 1, character=name.column),
        end=types.Position(line=name.line - 1,
                           character=name.column + len(name.name))
    )


def _get_locations(defs: List[Name]) -> List[types.Location]:
    return [
        types.Location(
            uri=d.module_path.absolute().as_uri(),
            range=_get_name_range(d)
        )
        for d in defs if d.module_path
    ]


@server.feature(DEFINITION)
def definition(
        ls: LanguageServer,
        params: types.TextDocumentPositionParams) -> List[types.Location]:
    script = get_script(ls, params.text_document.uri)
    defs = script.goto(params.position.line + 1, params.position.character)
    return _get_locations(defs)


@server.feature(REFERENCES)
def references(ls: LanguageServer,
               params: types.ReferenceParams) -> List[types.Location]:
    script = get_script(ls, params.text_document.uri)
    refs = script.get_references(params.position.line + 1,
                                 params.position.character)
    return _get_locations(refs)


@server.feature(WORKSPACE_DID_CHANGE_CONFIGURATION)
def did_change_configuration(ls: LanguageServer,
                             settings: types.DidChangeConfigurationParams):
    if not settings.settings or 'anakinls' not in settings.settings:
        return
    conf = settings.settings['anakinls']
    changed = set()
    for k in config:
        if k not in conf:
            continue
        config[k] = v = conf[k]
        if k == 'help_on_hover':
            global jediHoverFunction
            if v:
                jediHoverFunction = Script.help
            else:
                jediHoverFunction = Script.infer
        elif k == 'completion_snippet_first':
            global completionPrefixPlain
            global completionPrefixSnippet
            if v:
                completionPrefixPlain = 'z'
                completionPrefixSnippet = 'a'
            else:
                completionPrefixPlain = 'a'
                completionPrefixSnippet = 'z'
        else:
            changed.add(k)
    if 'jedi_settings' in conf:
        for key, value in conf['jedi_settings'].items():
            setattr(jedi_settings, key, value)

    if 'pycodestyle_config' in changed:
        pycodestyleOptions.clear()
    if 'mypy_enabled' in changed:
        mypyConfigs.clear()
    if changed and config['diagnostic_on_open']:
        for uri in ls.workspace.documents:
            _validate(ls, uri)


@server.feature(TEXT_DOCUMENT_WILL_SAVE)
def will_save(ls: LanguageServer, params: types.WillSaveTextDocumentParams):
    pass


@server.feature(TEXT_DOCUMENT_DID_SAVE,
                types.TextDocumentSaveRegistrationOptions(include_text=False))
def did_save(ls: LanguageServer, params: types.DidSaveTextDocumentParams):
    if config['diagnostic_on_save']:
        _validate(ls, params.text_document.uri)


_DOCUMENT_SYMBOL_KINDS = {
    'module': types.SymbolKind.Module,
    'class': types.SymbolKind.Class,
    'function': types.SymbolKind.Function,
    'statement': types.SymbolKind.Variable,
    'instance': types.SymbolKind.Variable,
    '_pseudotreenameclass': types.SymbolKind.Class
}


def _get_document_symbols(
        code_lines: List[str],
        names: List[Name],
        current: Optional[Name] = None
) -> List[types.DocumentSymbol]:
    # Looks like names are sorted by order of appearance, so
    # children are after their parents
    result = []
    while names:
        if current and names[0].parent() != current:
            break
        name = names.pop(0)
        if name.type == 'param':
            continue
        children = _get_document_symbols(
            code_lines,
            names,
            name
        )
        line = name.line - 1
        r = types.Range(
            start=types.Position(line=line, character=name.column),
            end=types.Position(line=line, character=len(code_lines[line]) - 1)
        )
        result.append(types.DocumentSymbol(
            name=name.name,
            kind=_DOCUMENT_SYMBOL_KINDS.get(name.type, types.SymbolKind.Null),
            range=r,
            selection_range=r,
            children=children or None
        ))
    return result


def _document_symbol_hierarchy(
        uri: str, code_lines: List[str], names: List[Name]
) -> List[types.DocumentSymbol]:
    return _get_document_symbols(code_lines, names)


def _document_symbol_plain(
        uri: str, code_lines: List[str], names: List[Name]
) -> List[types.SymbolInformation]:
    def _symbols():
        for name in names:
            if name.type == 'param':
                continue
            parent = name.parent()
            parent_name = parent and parent.full_name
            if parent_name:
                module_name = name.module_name
                if parent_name == module_name:
                    parent_name = None
                elif parent_name.startswith(f'{module_name}.'):
                    parent_name = parent_name[len(module_name) + 1:]
            yield types.SymbolInformation(
                name=name.name,
                kind=_DOCUMENT_SYMBOL_KINDS.get(name.type,
                                                types.SymbolKind.Null),
                location=types.Location(uri=uri, range=types.Range(
                    start=types.Position(line=name.line - 1,
                                         character=name.column),
                    end=types.Position(
                        line=name.line - 1,
                        characret=len(code_lines[name.line - 1]) - 1))),
                container_name=parent_name
            )
    return list(_symbols())


@server.feature(DOCUMENT_SYMBOL)
def document_symbol(
        ls: LanguageServer, params: types.DocumentSymbolParams
) -> Union[List[types.DocumentSymbol], List[types.SymbolInformation], None]:
    script = get_script(ls, params.text_document.uri)
    names = script.get_names(all_scopes=True)
    if not names:
        return None
    global documentSymbolFunction
    result = documentSymbolFunction(
        params.text_document.uri,
        script._code_lines,
        script.get_names(all_scopes=True)
    )
    return result


def _get_text_edits(diff: str) -> List[types.TextEdit]:
    result = []
    line_number = 0
    start = None
    replace_lines = False
    lines: List[str] = []

    def _append():
        if replace_lines:
            end = types.Position(line=line_number, character=0)
        else:
            end = start
        result.append(
            types.TextEdit(
                range=types.Range(start=start, end=end),
                new_text=''.join(lines)))

    for line in diff.splitlines(True)[2:]:
        kind = line[0]
        if kind == '-':
            if not start:
                start = types.Position(line=line_number, character=0)
            replace_lines = True
            line_number += 1
            continue
        if kind == '+':
            if not start:
                start = types.Position(line=line_number, character=0)
            lines.append(line[1:])
            continue
        if start:
            _append()
            start = None
            replace_lines = False
            lines = []
        if kind == '@':
            line_number = int(line[4:line.index(',')]) - 1
        else:
            line_number += 1
    if start:
        _append()
    return result


def _get_document_changes(
        ls: LanguageServer, refactoring: Refactoring
) -> List[types.TextDocumentEdit]:
    result = []
    for fn, changes in refactoring.get_changed_files().items():
        text_edits = _get_text_edits(changes.get_diff())
        if text_edits:
            uri = fn.absolute().as_uri()
            result.append(types.TextDocumentEdit(
                text_document=types.VersionedTextDocumentIdentifier(
                    uri=uri,
                    version=ls.workspace.get_document(uri).version
                ),
                edits=text_edits
            ))
    return result


@server.feature(CODE_ACTION, types.CodeActionOptions(
    code_action_kinds=[
        types.CodeActionKind.RefactorInline,
        types.CodeActionKind.RefactorExtract]))
def code_action(
        ls: LanguageServer, params: types.CodeActionParams
) -> Optional[List[types.CodeAction]]:
    if params.range.start != params.range.end:
        # No selection actions
        return None
    script = get_script(ls, params.text_document.uri)
    try:
        refactoring = script.inline(params.range.start.line + 1,
                                    params.range.start.character)
    except RefactoringError:
        return None
    document_changes = _get_document_changes(ls, refactoring)
    if document_changes:
        return [types.CodeAction(
            title='Inline variable',
            kind=types.CodeActionKind.RefactorInline,
            edit=types.WorkspaceEdit(document_changes=document_changes))]
    return None


def _formatting(
        ls: LanguageServer, uri: str, range_: types.Range = None
) -> Optional[List[types.TextEdit]]:
    old = get_script(ls, uri)._code
    lines = [(range_.start.line + 1, range_.end.line + 1)] if range_ else None
    diff, changed = FormatCode(old, style_config=config['yapf_style_config'],
                               lines=lines, print_diff=True)
    if not changed:
        return None
    return _get_text_edits(diff)


@server.feature(FORMATTING)
def formatting(
        ls: LanguageServer, params: types.DocumentFormattingParams
) -> Optional[List[types.TextEdit]]:
    return _formatting(ls, params.text_document.uri)


@server.feature(RANGE_FORMATTING)
def range_formatting(
        ls: LanguageServer, params: types.DocumentRangeFormattingParams
) -> Optional[List[types.TextEdit]]:
    return _formatting(ls, params.text_document.uri, params.range)


@server.feature(RENAME)
def rename(ls: LanguageServer,
           params: types.RenameParams) -> Optional[types.WorkspaceEdit]:
    script = get_script(ls, params.text_document.uri)
    try:
        refactoring = script.rename(params.position.line + 1,
                                    params.position.character,
                                    new_name=params.new_name)
    except RefactoringError:
        return None
    document_changes = _get_document_changes(ls, refactoring)
    if document_changes:
        return types.WorkspaceEdit(document_changes=document_changes)
    return None


@server.feature(DOCUMENT_HIGHLIGHT)
def highlight(
        ls: LanguageServer, params: types.TextDocumentPositionParams
) -> Optional[List[types.DocumentHighlight]]:
    script = get_script(ls, params.text_document.uri)
    names = script.get_references(params.position.line + 1,
                                  params.position.character,
                                  scope='file')
    if not names:
        return None
    return [
        types.DocumentHighlight(
            range=_get_name_range(name)
        )
        for name in names
    ]
