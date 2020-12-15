# anakin-language-server
Yet another Jedi Python language server

## Requirements

- Python >= 3.6
- pygls ~= 0.9
- Jedi >= 0.17.1
- pyflakes ~= 2.2
- pycodestyle ~= 2.5
- yapf ~=0.30

## Optional requirements
- mypy

## Implemented features

- `textDocument/completion`
- `textDocument/hover`
- `textDocument/signatureHelp`
- `textDocument/definition`
- `textDocument/references`
- `textDocument/publishDiagnostics`
- `textDocument/documentSymbol`
- `textDocument/codeAction` ([Inline variable](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.inline))
- `textDocument/formatting`
- `textDocument/rangeFormatting`
- `textDocument/rename`
- `textDocument/documentHighlight`

## Initialization option

- `venv` - path to virtualenv. This option will be passed to Jedi's [create\_environment](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.create_environment).

Also one can set `VIRTUAL_ENV` or `CONDA_PREFIX` before running `anakinls` so Jedi will find proper environment. See [get\_default\_environment](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.get_default_environment).


## Diagnostics

Diagnostics are published on document open and save.

Diagnostics providers:

- **Jedi**

  See [get\_syntax\_errors](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.get_syntax_errors).

- **pyflakes**
- **pycodestyle**

  Server restart is needed after changing one of the [configuration files](https://pycodestyle.pycqa.org/en/latest/intro.html#configuration).

- **mypy**

  Install `mypy` in the same environment as `anakinls` and set `mypy_enabled` configuration option.

## Configuration options

Configuration options must be passed under `anakinls` key in `workspace/didChangeConfiguration` notification.

Available options:

|Option|Description|Default|
|-|-|-|
|`help_on_hover`|Use [`help`](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.help) instead of [`infer`](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.infer) for `textDocument/hover`.|`True`|
|`completion_snippet_first`|Tweak `sortText` property so snippet completion appear before plain completion.|`False`|
|`completion_fuzzy`|Value of the `fuzzy` parameter for [`complete`](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.complete).|`False`|
|`diagnostic_on_open`|Publish diagnostics on `textDocument/didOpen`|`True`|
|`diagnostic_on_change`|Publish diagnostics on `textDocument/didChange`|`False`|
|`diagnostic_on_save`|Publish diagnostics on `textDocument/didSave`|`True`|
|`pyflakes_errors`|Diagnostic severity will be set to `Error` if Pyflakes message class name is in this list. See [Pyflakes messages](https://github.com/PyCQA/pyflakes/blob/master/pyflakes/messages.py).|`['UndefinedName']`|
|`pycodestyle_config`|In addition to project and user level config, specify pycodestyle config file. Same as `--config` option for `pycodestyle`.|`None`|
|`mypy_enabled`|Use [`mypy`](https://mypy.readthedocs.io/en/stable/index.html) to provide diagnostics.|`False`|
|`yapf_style_config`|Either a style name or a path to a file that contains formatting style settings.|`'pep8'`|

## Configuration example

Here is [eglot](https://github.com/joaotavora/eglot) configuration:

```elisp
(defvar my/lsp-venv nil
  "Name of virtualenv.
Set it in project's dir-locals file.")

(defclass my/eglot-anakinls (eglot-lsp-server) ()
  :documentation
  "Own eglot server class.")

(cl-defmethod eglot-initialization-options ((_server my/eglot-anakinls))
  "Pass initialization param to anakinls."
  `(:venv ,(when my/lsp-venv
             (expand-file-name
              (concat "~/.virtualenvs/" my/lsp-venv)))))

;; Add this server to eglot programs to handle python-mode and run `anakinls'
(add-to-list 'eglot-server-programs
             '(python-mode my/eglot-anakinls "anakinls"))

;; Also treat UnusedVariable as error
(setq-default eglot-workspace-configuration
              '((:anakinls :pyflakes_errors ["UndefinedName" "UnusedVariable"])))

```

## Installation

```
pip install anakin-language-server
```
