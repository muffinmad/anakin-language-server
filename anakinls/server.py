import logging

from inspect import Parameter
from typing import List

from jedi import Script, create_environment, get_default_environment, settings
from jedi.api.classes import Definition

from pygls.features import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
                            TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,
                            INITIALIZE, HOVER, SIGNATURE_HELP, DEFINITION,
                            REFERENCES)
from pygls import types
from pygls.server import LanguageServer
from pygls.uris import from_fs_path


_COMPLETION_TYPES = {
    'module': types.CompletionItemKind.Module,
    'class': types.CompletionItemKind.Class,
    'instance': types.CompletionItemKind.Reference,
    'function': types.CompletionItemKind.Function,
    'param': types.CompletionItemKind.Variable,
    'path': types.CompletionItemKind.Text,
    'keyword': types.CompletionItemKind.Keyword,
    'statement': types.CompletionItemKind.Keyword
}


class AnakinLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'anakinls'
    jediEnvironment = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        settings.case_insensitive_completion = False

        @self.feature(INITIALIZE)
        def initialize(params: types.InitializeParams):
            venv = getattr(params.initializationOptions, 'venv', None)
            if venv:
                self.jediEnvironment = create_environment(venv, False)
            else:
                self.jediEnvironment = get_default_environment()
            logging.info(f'Jedi environment python: {self.jediEnvironment.executable}')
            logging.info(f'Jedi environment sys_path:')
            for p in self.jediEnvironment.get_sys_path():
                logging.info(f'  {p}')


server = AnakinLanguageServer()
scripts = {}


def get_script(ls: AnakinLanguageServer, uri: str, update: bool = False) -> Script:
    result = None if update else scripts.get(uri)
    if not result:
        document = ls.workspace.get_document(uri)
        result = Script(
            source=document.source,
            path=document.path,
            environment=ls.jediEnvironment
        )
        scripts[uri] = result
    return result


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: types.DidOpenTextDocumentParams):
    get_script(ls, params.textDocument.uri)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls, params: types.DidCloseTextDocumentParams):
    try:
        del scripts[params.textDocument.uri]
    except KeyError:
        pass


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: types.DidChangeTextDocumentParams):
    get_script(ls, params.textDocument.uri, True)


def get_completion_kind(ls: LanguageServer, completion_type: str) -> types.CompletionItemKind:
    if completion_type not in _COMPLETION_TYPES:
        ls.show_message(f'Unknown completion type {completion_type}')
        return types.CompletionItemKind.Text
    return _COMPLETION_TYPES[completion_type]


@server.feature(COMPLETION, trigger_characters=['.'])
def completions(ls: LanguageServer, params: types.CompletionParams = None):
    script = get_script(ls, params.textDocument.uri)
    completions = script.complete(
        params.position.line + 1,
        params.position.character
    )

    def _key(completion):
        return (
            completion.name.startswith('__'),
            completion.name.startswith('_'),
            completion.name
        )

    def _completions():
        for completion in sorted(completions, key=_key):
            item = dict(
                label=completion.name,
                kind=get_completion_kind(ls, completion.type),
                documentation=completion.docstring(raw=True)
            )
            yield types.CompletionItem(**item)
            for signature in completion.get_signatures():
                names = []
                snippets = []
                for i, param in enumerate(signature.params):
                    if '=' in param.description or param.kind == Parameter.VAR_KEYWORD:
                        break
                    if param.name == '/':
                        continue
                    names.append(param.name)
                    if param.kind == Parameter.KEYWORD_ONLY:
                        snippet_prefix = f'{param.name}='
                    else:
                        snippet_prefix = ''
                    snippets.append(f'{snippet_prefix}${{{i + 1}:{param.name}}}')
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
def hover(ls, params: types.TextDocumentPositionParams) -> types.Hover:
    script = get_script(ls, params.textDocument.uri)
    infer = script.infer(params.position.line + 1, params.position.character)
    if infer:
        result = infer[0].docstring()
        if result:
            return types.Hover(types.MarkupContent(types.MarkupKind.PlainText, result))


@server.feature(SIGNATURE_HELP)
def signature_help(ls, params: types.TextDocumentPositionParams) -> types.SignatureHelp:
    script = get_script(ls, params.textDocument.uri)
    signatures = script.get_signatures(params.position.line + 1, params.position.character)

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


def _get_locations(defs: List[Definition]) -> List[types.Location]:
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
def definition(ls, params: types.TextDocumentPositionParams) -> List[types.Location]:
    script = get_script(ls, params.textDocument.uri)
    defs = script.goto(params.position.line + 1, params.position.character)
    return _get_locations(defs)


@server.feature(REFERENCES)
def references(ls, params: types.ReferenceParams) -> List[types.Location]:
    script = get_script(ls, params.textDocument.uri)
    refs = script.get_references(params.position.line + 1, params.position.character)
    return _get_locations(refs)
