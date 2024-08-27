# NEWS

## 1.22

- Use pygls v1.3


## 1.17

- Migrating to pygls v1.1

## 1.16

- Use version 0 for not opened files on rename

## 1.15

- Fix one more typo causing Jedi errors not appear in diagnostics

## 1.14

- Fix typo causing Jedi errors not appear in diagnostics

## 1.13

- Use pygls 0.10.2
- Faster document changes builder

## 1.12

- Use Jedi v0.18

## 1.11

- Expose an interface so that the user can adjust Jedi configuration
- Case insensitive completions

## 1.10.3

- `create_environment` takes 1 positional argument

## 1.10.2

- Handle `pathlib.Path` from `jedi` (#17)

## 1.10.1

- Handle missed `initializationOptions`

## 1.10

- Publish diagnostics on document change
- Options to control diagnoatics publishing

## 1.9

- Fuzzy completions

## 1.8.2

- Don't pass `[None]` as paths to pycodestyle

## 1.8.1

- Bind Jedi's completion type `property` to `CompletionItemKind.Property`

## 1.8

- Implement `textDocument/documentHighlight`
- Invalid syntax error message

## 1.7

- Implement `textDocument/rename`

## 1.6

- Implement `textDocument/formatting` and `textDocument/rangeFormatting` using `yapf` (#12)

## 1.5.2

- Make Jedi's `statement` have `Variable` type in the completion (#14)
- Add serverInfo and --version CLI arg (#8)
- Possibility to place snippet completion before plain one (#10)

## 1.5.1

- Hover info in markdown format

## 1.5

- "Inline variable" code action

## 1.4.1

- `textEdit` in `completionItem` must replace to the end of word
- Strip leading `'` from `completionItem` label

## 1.4

- Implement `textDocument/documentSymbol`
- Don't return snippets in completions if client doesn't support them

## 1.3.2

- Provide `textEdit` for `CompletionItem`

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
