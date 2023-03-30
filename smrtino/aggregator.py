class aggregator:
    """A light wrapper around a list to save some typing when building
       a list of lines to be printed.
    """
    def __init__(self, *args):
        self._list = list()
        if args:
            self(*args)

    def __call__(self, *args):
        self._list.extend([str(a) for a in args] or [''])

    def __iter__(self, *args):
        return iter(self._list)

