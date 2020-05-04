import logging

from inspect import Parameter
from typing import List, Dict, Optional, Any

from jedi import (Script, create_environment, get_default_environment,
                  settings as jedi_settings, get_default_project)
from jedi.api.classes import Name

from pycodestyle import (BaseReport as CodestyleBaseReport,
                         Checker as CodestyleChecker,
                         StyleGuide as CodestyleStyleGuide)

from pyflakes.api import check as pyflakes_check

from pygls.features import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
                            TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,
                            HOVER, SIGNATURE_HELP, DEFINITION,
                            REFERENCES, WORKSPACE_DID_CHANGE_CONFIGURATION,
                            TEXT_DOCUMENT_WILL_SAVE, TEXT_DOCUMENT_DID_SAVE)
from pygls import types
from pygls.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.uris import from_fs_path, to_fs_path


_COMPLETION_TYPES = {
    'module': types.CompletionItemKind.Module,
    'class': types.CompletionItemKind.Class,
    'instance': types.CompletionItemKind.Reference,
    'function': types.CompletionItemKind.Function,
    'param': types.CompletionItemKind.Variable,
    'keyword': types.CompletionItemKind.Keyword,
    'statement': types.CompletionItemKind.Keyword
}


jedi_settings.case_insensitive_completion = False


class AnakinLanguageServerProtocol(LanguageServerProtocol):

    def bf_initialize(
            self, params: types.InitializeParams) -> types.InitializeResult:
        result = super().bf_initialize(params)

        global jediEnvironment
        global jediProject
        venv = getattr(params.initializationOptions, 'venv', None)
        if venv:
            jediEnvironment = create_environment(venv, False)
        else:
            jediEnvironment = get_default_environment()
        jediProject = get_default_project(getattr(params, 'rootPath', None))
        logging.info(f'Jedi environment python: {jediEnvironment.executable}')
        logging.info('Jedi environment sys_path:')
        for p in jediEnvironment.get_sys_path():
            logging.info(f'  {p}')
        logging.info(f'Jedi project path: {jediProject._path}')

        result.capabilities.textDocumentSync = types.TextDocumentSyncOptions(
            open_close=True,
            change=types.TextDocumentSyncKind.INCREMENTAL,
            save=types.SaveOptions()
        )
        return result


server = LanguageServer(protocol_cls=AnakinLanguageServerProtocol)
scripts: Dict[str, Script] = {}
pycodestyleOptions: Dict[str, Any] = {}
mypyConfigs: Dict[str, str] = {}
jediEnvironment = None
jediProject = None
config = {
    'pyflakes_errors': [
        'UndefinedName'
    ],
    'help_on_hover': True,
    'mypy_enabled': False
}


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
            types.Range(types.Position(), types.Position()),
            msg,
            types.DiagnosticSeverity.Error,
            source='pyflakes'
        ))

    def _get_codeline(self, line):
        return self.script._code_lines[line].rstrip('\n\r')

    def syntaxError(self, _filename, msg, lineno, offset, _text):
        line = lineno - 1
        col = offset or 0
        self.result.append(types.Diagnostic(
            types.Range(
                types.Position(line, col),
                types.Position(line, len(self._get_codeline(line)) - col)
            ),
            msg,
            types.DiagnosticSeverity.Error,
            source='pyflakes'
        ))

    def flake(self, message):
        line = message.lineno - 1
        if message.__class__.__name__ in self.errors:
            severity = types.DiagnosticSeverity.Error
        else:
            severity = types.DiagnosticSeverity.Warning
        self.result.append(types.Diagnostic(
            types.Range(
                types.Position(line, message.col),
                types.Position(line, len(self._get_codeline(line)))
            ),
            message.message % message.message_args,
            severity,
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
            types.Range(
                types.Position(line, offset),
                types.Position(line, len(self.lines[line].rstrip('\n\r')))
            ),
            text,
            types.DiagnosticSeverity.Warning,
            code,
            'pycodestyle'
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
        result = CodestyleStyleGuide(paths=[folder]).options
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
    filename = to_fs_path(uri)
    lines = api.run([
        '--python-executable', jediEnvironment.executable,
        '--python-version', f'{version_info.major}.{version_info.minor}',
        '--config-file', get_mypy_config(ls, uri),
        '--hide-error-context',
        '--show-column-numbers',
        '--show-error-codes',
        '--no-pretty',
        '--show-absolute-path',
        '--no-error-summary',
        filename
    ])
    if lines[1]:
        ls.show_message(lines[1], types.MessageType.Error)
        return

    for line in lines[0].split('\n'):
        parts = line.split(':', 4)
        if len(parts) < 5:
            continue
        fn, row, column, err_type, message = parts
        if fn != filename:
            continue
        row = int(row) - 1
        column = int(column) - 1
        if err_type.strip() == 'note':
            severity = types.DiagnosticSeverity.Hint
        else:
            severity = types.DiagnosticSeverity.Warning
        result.append(
            types.Diagnostic(
                types.Range(
                    types.Position(row, column),
                    types.Position(row, len(script._code_lines[row]))
                ),
                message.strip(),
                severity,
                source='mypy'
            )
        )
    return result


def _validate(ls: LanguageServer, uri: str):
    # Jedi
    script = get_script(ls, uri)
    result = [
        types.Diagnostic(
            types.Range(
                types.Position(x.line - 1, x.column),
                types.Position(x.until_line - 1, x.until_column)
            ),
            'Invalid syntax',
            types.DiagnosticSeverity.Error,
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

    if config['mypy_enabled']:
        try:
            _mypy_check(ls, uri, script, result)
        except Exception as e:
            ls.show_message(f'mypy check error: {e}',
                            types.MessageType.Warning)

    ls.publish_diagnostics(uri, result)


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams):
    _validate(ls, params.textDocument.uri)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: LanguageServer, params: types.DidCloseTextDocumentParams):
    try:
        del scripts[params.textDocument.uri]
    except KeyError:
        pass


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams):
    get_script(ls, params.textDocument.uri, True)


@server.feature(COMPLETION, trigger_characters=['.'])
def completions(ls: LanguageServer, params: types.CompletionParams):
    script = get_script(ls, params.textDocument.uri)
    completions = script.complete(
        params.position.line + 1,
        params.position.character
    )

    def sort_key(completion):
        name = completion.name
        if name.startswith('__'):
            return f'zz{name}'
        if name.startswith('_'):
            return f'za{name}'
        return f'aa{name}'

    def _completions():
        for completion in completions:
            item = dict(
                label=completion.name,
                kind=_COMPLETION_TYPES.get(completion.type,
                                           types.CompletionItemKind.Text),
                documentation=completion.docstring(raw=True),
                sort_text=sort_key(completion)
            )
            yield types.CompletionItem(**item)
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
                    label=f'{completion.name}({names_str})',
                    insert_text=f'{completion.name}({snippets_str})$0',
                    insert_text_format=2
                ))

    return types.CompletionList(False, list(_completions()))


@server.feature(HOVER)
def hover(ls: LanguageServer,
          params: types.TextDocumentPositionParams) -> Optional[types.Hover]:
    script = get_script(ls, params.textDocument.uri)
    fn = script.help if config['help_on_hover'] else script.infer
    names = fn(params.position.line + 1, params.position.character)
    result = '\n----------\n'.join(x.docstring() for x in names)
    if result:
        return types.Hover(
            types.MarkupContent(types.MarkupKind.PlainText, result)
        )
    return None


@server.feature(SIGNATURE_HELP, trigger_characters=['(', ','])
def signature_help(
        ls: LanguageServer,
        params: types.TextDocumentPositionParams
) -> Optional[types.SignatureHelp]:
    script = get_script(ls, params.textDocument.uri)
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
            signature.to_string(),
            parameters=[
                types.ParameterInformation(param.name)
                for param in signature.params
            ]
        ))
        if signature.index > param_idx:
            param_idx = signature.index
            idx = i
        i += 1
    if result:
        return types.SignatureHelp([result[idx]], 0, param_idx)
    return None


def _get_locations(defs: List[Name]) -> List[types.Location]:
    return [
        types.Location(
            from_fs_path(d.module_path),
            types.Range(
                types.Position(d.line - 1, d.column),
                types.Position(d.line - 1, d.column + len(d.name))
            )
        )
        for d in defs if d.module_path
    ]


@server.feature(DEFINITION)
def definition(
        ls: LanguageServer,
        params: types.TextDocumentPositionParams) -> List[types.Location]:
    script = get_script(ls, params.textDocument.uri)
    defs = script.goto(params.position.line + 1, params.position.character)
    return _get_locations(defs)


@server.feature(REFERENCES)
def references(ls: LanguageServer,
               params: types.ReferenceParams) -> List[types.Location]:
    script = get_script(ls, params.textDocument.uri)
    refs = script.get_references(params.position.line + 1,
                                 params.position.character)
    return _get_locations(refs)


@server.feature(WORKSPACE_DID_CHANGE_CONFIGURATION)
def did_change_configuration(ls: LanguageServer,
                             settings: types.DidChangeConfigurationParams):
    if not settings.settings or not hasattr(settings.settings, 'anakinls'):
        return
    for k in config:
        if hasattr(settings.settings.anakinls, k):
            config[k] = getattr(settings.settings.anakinls, k)


@server.feature(TEXT_DOCUMENT_WILL_SAVE)
def will_save(ls: LanguageServer, params: types.WillSaveTextDocumentParams):
    pass


@server.feature(TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: LanguageServer, params: types.DidSaveTextDocumentParams):
    _validate(ls, params.textDocument.uri)
