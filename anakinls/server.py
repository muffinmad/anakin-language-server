import logging

from inspect import Parameter

from jedi import Script, create_environment, get_default_environment, settings

from pygls.features import (COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
                            TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,
                            INITIALIZE)
from pygls.server import LanguageServer
from pygls.types import (CompletionItem, CompletionList, CompletionParams,
                         CompletionItemKind,
                         ConfigurationItem, ConfigurationParams, Diagnostic,
                         DidChangeTextDocumentParams, DidCloseTextDocumentParams,
                         DidOpenTextDocumentParams,
                         MessageType, Position, Range,
                         TextDocumentIdentifier,
                         InitializeParams)

_COMPLETION_TYPES = {
    'module': CompletionItemKind.Module,
    'class': CompletionItemKind.Class,
    'instance': CompletionItemKind.Reference,
    'function': CompletionItemKind.Function,
    'param': CompletionItemKind.Variable,
    'path': CompletionItemKind.Text,
    'keyword': CompletionItemKind.Keyword,
    'statement': CompletionItemKind.Keyword
}


class AnakinLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'anakinls'
    jediEnvironment = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        settings.case_insensitive_completion = False

        @self.feature(INITIALIZE)
        def initialize(params: InitializeParams):
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
async def did_open(ls, params: DidOpenTextDocumentParams):
    get_script(ls, params.textDocument.uri)


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls, params: DidCloseTextDocumentParams):
    try:
        del scripts[params.textDocument.uri]
    except KeyError:
        pass


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: DidChangeTextDocumentParams):
    get_script(ls, params.textDocument.uri, True)


def get_completion_kind(ls: LanguageServer, completion_type: str) -> CompletionItemKind:
    if completion_type not in _COMPLETION_TYPES:
        ls.show_message(f'Unknown completion type {completion_type}')
        return CompletionItemKind.Text
    return _COMPLETION_TYPES[completion_type]


@server.feature(COMPLETION, trigger_characters=['.'])
def completions(ls: LanguageServer, params: CompletionParams = None):
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
            yield CompletionItem(**item)
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
                yield CompletionItem(**dict(
                    item,
                    label=f'{completion.name}({names_str})',
                    insert_text=f'{completion.name}({snippets_str})$0',
                    insert_text_format=2
                ))

    return CompletionList(False, list(_completions()))
