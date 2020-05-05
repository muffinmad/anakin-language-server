# NEWS

## 1.3.1

- Possibility to specify pycodestyle config file

## 1.3

- Optionally use mypy to provide diagnostics

## 1.2.8

- Make `TextDocumentSyncOptions.save` a `SaveOptions`

## 1.2.7

- Search pycodestyle configuration in workspace folders (#3)

## 1.2.6

- Don't double initialize Jedi environment and project

## 1.2.5

- Provide `sortText` in `CompletionItem`

## 1.2.4

- Pass `TextDocumentSyncOptions` in `textDocumentSync` (#2)

## 1.2.3

- Signature help trigger characters (#4)

## 1.2.2

- Set diagnostic end column to line width (#1)

## 1.2.1

- Add `help_on_hover` configuration option

## 1.2

- Use `script.help()` to provide hover info

## 1.1.1

- Use pygls 0.9

## 1.1

- Cache Jedi's Scripts
- Implement `textDocument/hover`
- Implement `textDocument/signatureHelp`
- Implement `textDocument/definition`
- Implement `textDocument/references`
- Implement `textDocument/publishDiagnostics`. Diagnostics by pycodestyle and pyflakes
- Use Jedi 0.17

## 1.0

- Implement `textDocument/completion`
- `venv` initialization option
