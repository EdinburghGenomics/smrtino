#!python

"""
I want to permit dumping of OrderedDict and defaultdict with
yaml.safe_dump().
The OrderedDict will be dumped as a regular dict but in order.
I don't care about how the YAML is loaded, nor how the OrderedDict
is represented with regular yaml.dump().

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

yamlloader.ordereddict.CSafeDumper.add_representer(defaultdict, real_yaml.dumper.SafeDumper.represent_dict)
