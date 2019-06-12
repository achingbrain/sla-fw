try:
    # Python2
    import __builtin__ as builtins
except:
    # Python 3
    import builtins as builtins


def _identity(message):
    return message


def fake_gettext():
    builtins._ = _identity
    builtins.N_ = _identity




