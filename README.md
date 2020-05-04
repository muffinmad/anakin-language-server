# anakin-language-server
Yet another Jedi Python language server

## Requirements

- Python >= 3.6
- pygls ~= 0.9
- Jedi ~= 0.17
- pyflakes ~= 2.2
- pycodestyle ~= 2.5

## Implemented features

- `textDocument/completion`
- `textDocument/hover`
- `textDocument/signatureHelp`
- `textDocument/definition`
- `textDocument/references`
- `textDocument/publishDiagnostics`

## Initialization option

- `venv` - path to virtualenv. This option will be passed to Jedi's [create\_environment](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.create_environment).

Also one can set `VIRTUAL_ENV` or `CONDA_PREFIX` before running `anakinls` so Jedi will find proper environment. See [get\_default\_environment](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.get_default_environment).


## Diagnostics

Diagnostics are published on document open and save.

Diagnostics providers:

- Jedi. See [get\_syntax\_errors](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.get_syntax_errors).
- pyflakes
- pycodestyle. Server restart is needed after changing one of the [configuration files](https://pycodestyle.pycqa.org/en/latest/intro.html#configuration).

## Configuration options

Configuration options must be passed under `anakinls` key in `workspace/didChangeConfiguration` notification.

Available options:
- `pyflakes_errors` - Diagnostic severity will be set to `Error` if Pyflakes message class name is in this list. See [Pyflakes messages](https://github.com/PyCQA/pyflakes/blob/master/pyflakes/messages.py).
  Default: `['UndefinedName']`.
- `help_on_hover` - Use [`help`](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.help) instead of [`infer`](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.infer) for `textDocument/hover`.
  Default: `True`.

## Example

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
