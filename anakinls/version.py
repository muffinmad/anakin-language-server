import pkg_resources


def get_version() -> str:
    "Return the version of anakinls."
    r = pkg_resources.require('anakin-language-server')
    return r[0].version
