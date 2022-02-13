"""Implementation of the plugin system

The Plugin class itself shouldn't be used.
Direct subclasses (such as ModelReprPlugin) should be, like:

    ps = ModelReprPlugin.get_plugins()  # returns a dict uid -> plugin class
    html = ps['table/2'].repr_model(1, clyngor_model)

"""
import os
import glob
import importlib


class Plugin:
    @staticmethod
    def get_plugins(path: str):
        for pyfile in glob.glob(os.path.join('plugins/', path, '*.py')):
            pymod = os.path.splitext(pyfile.replace('/', '.'))[0]
            module = importlib.import_module(pymod)
            # print(pymod, module)
            for name, obj in vars(module).items():
                if name.startswith('_'): continue
                if type(obj) is type and issubclass(obj, Plugin) and obj not in globals().values():
                    yield obj.OPTIONS.get('kind', name), obj

    def __init__(self, given_options: dict):
        options = with_keys_as_id(getattr(self.__class__, 'OPTIONS', {}))
        options.update(with_keys_as_id(given_options))  # erase default values with given option values
        self.options = type('options', (), options)  # access is option.optname instead of option['optname']

    def init(self):
        """to be overwritten by plugins if necessary.
        It should be called at the end of __init__ calls chain"""
        pass

def with_keys_as_id(d: dict) -> dict:
    """
    >>> with_keys_as_id({'a b': 1})
    {'a_b': 1}
    """
    return {k.replace(' ', '_'): v for k, v in d.items()}




class ModelReprPlugin(Plugin):

    @staticmethod
    def get_plugins():
        return dict(Plugin.get_plugins('model_repr/'))

    def __init__(self, given_options: dict, get_username_of: callable, get_choicename_of: callable):
        super().__init__(given_options)
        self.uid = getattr(self.options, 'kind', self.__class__.__name__)
        self.get_username_of, self.get_choicename_of = get_username_of, get_choicename_of
        self.init()

    def repr_model(self, *args, **kwargs):
        ret = getattr(self, 'on_model', lambda *a, **k: '')(*args, **kwargs)
        return ret if isinstance(ret, str) else ''.join(map(str, ret))  # handle generator, lists,…

    def repr_header(self, *args, **kwargs):
        ret = getattr(self, 'on_header', lambda *a, **k: '')(*args, **kwargs)
        return ret if isinstance(ret, str) else ''.join(map(str, ret))  # handle generator, lists,…

    def repr_footer(self, *args, **kwargs):
        ret = getattr(self, 'on_footer', lambda *a, **k: '')(*args, **kwargs)
        return ret if isinstance(ret, str) else ''.join(map(str, ret))  # handle generator, lists,…
