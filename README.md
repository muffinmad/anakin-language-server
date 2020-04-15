# anakin-language-server
Yet another Jedi Python language server

## Requirements

- Python >= 3.6
- pygls == 0.8.1
- Jedi == 0.17.0

## Implemented features

- `textDocument/completion`
- `textDocument/hover`
- `textDocument/signatureHelp`
- `textDocument/definition`
- `textDocument/references`
- `textDocument/publishDiagnostics`

## Initialization option

- `venv` - path to virtualenv

Also one can set `VIRTUAL_ENV` or `CONDA_PREFIX` before running `anakinls` so Jedi will find proper environment. See [get\_default\_environment](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.get_default_environment).


## Diagnostics

Diagnostics are published on document open and save.

Diagnostics provides:

- Jedi. See [get\_syntax\_errors](https://jedi.readthedocs.io/en/latest/docs/api.html#jedi.Script.get_syntax_errors).


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
```
