
from model_repr import ModelReprPlugin, get_plugin_by_name



class text(ModelReprPlugin):
    """Just a text, that will be formatted with string interpolation.

    See render_text() args to see which variables may be used in the text.

    """
    OPTIONS = {
        "kind": 'text',
        "text": '',
    }

    def render_text(self, uid=None, models=None, model=None, nb_models=None, compilation_runtime_repr=None, compilation_runtime=None, common_atoms=None):
        ns = dict(locals())
        exec('ret = f' + repr(self.options.text), ns)
        return ns['ret']

    def on_model(self, **kwargs):
        return self.render_text(**kwargs)
    on_header = on_footer = on_model  # same function


class title(ModelReprPlugin):
    OPTIONS = {
        "kind": 'title',
        "index": True,
        "uid": True,
        "title style": '<br/><h2>Solution{idx_repr}</h2>{uid_repr}<br/>',
        "uid style": '<b>— {uid} —</b><br/><br/>',
    }

    def on_model(self, idx: int, uid: str, model: object):
        """Return html representation of given model"""
        if uid == 'Green Velvet':
            uid = '<a href="https://www.youtube.com/watch?v=3_5oRtBDtfg#t=14.5s">Green Velvet</a>'
        uid_repr = self.options.uid_style.format(uid=uid) if self.options.uid else ''
        idx_repr = f' {idx}' if self.options.index else ''
        title_repr = self.options.title_style.format(idx_repr=idx_repr, uid_repr=uid_repr)
        return title_repr

    def on_header(self):
        return ''

    def on_footer(self):
        return ''
