#!python

"""
I want to permit dumping of OrderedDict and defaultdict with
yaml.safe_dump().
The OrderedDict will be dumped as a regular dict but in order.
I don't care about how the YAML is loaded.

As a new addition, defaultdict objects will also be dump-able as
regular dicts, sorted by key just like regular dicts.
This is handy where a defaultdict is embedded in an structure you
are dumping.

Both of these are lossy - you can restore neither the order of the
elements nor the special defaultdict behaviour.

To use it:

    from yaml_ordered import yaml

Then call yaml.safe_dump() etc. as normal. This used to just
monkey-patch the global YAML loader object but now it doesn't
do that any more - it uses yamlloader instead.

"""

import yaml as real_yaml
import yamlloader
from collections import defaultdict

class yaml:

    @classmethod
    def ordered_load(cls, *args, **kwargs):
        return real_yaml.load(*args, Loader=yamlloader.ordereddict.CSafeLoader, **kwargs)

    @classmethod
    def safe_load(cls, *args, **kwargs):
        return real_yaml.safe_load(*args, **kwargs)

    @classmethod
    def load(cls, *args, **kwargs):
        return real_yaml.safe_load(*args, **kwargs)

    @classmethod
    def safe_dump(cls, *args, **kwargs):
        return real_yaml.dump(*args, Dumper=yamlloader.ordereddict.CSafeDumper, **kwargs)

# Make all dicts be ordered on dump!
for t in dict, defaultdict:
    yamlloader.ordereddict.CSafeDumper.add_representer(t, yamlloader.ordereddict.CSafeDumper.represent_ordereddict)

def dictify(s):
    """Utility function to change all OrderedDict in a structure
       into a dict.
    """
    if any(isinstance(s, t) for t in [str, int, float, bool]):
        return s
    try:
        # Convert dict and dict-like things.
        return {k: dictify(v) for k, v in s.items()}
    except AttributeError:
        try:
            # List-like things that aren't strings
            return [ dictify(i) for i in s ]
        except Exception:
            # Give up and convert s to a str
            return str(s)

