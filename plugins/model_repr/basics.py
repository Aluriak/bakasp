
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


class copy2clipboard(ModelReprPlugin):
    OPTIONS = {
        'label': 'Copy',
        'label copied': 'Copied !',
        'label copied duration': 1000,  # in milliseconds
        'target': 'atoms',
        'button id': None,
    }
    def on_model(self, idx: int, uid: str, model: object):
        if self.options.target == 'atoms':
            text = repr(model.atoms).replace("'", '"').replace('"', r'\"')
            # text = uid
        elif self.options.target == 'title':
            text = f'Solution {idx} ({uid}) of {len(model)} atoms'
        elif self.options.target == 'uid':
            text = uid
        elif self.options.target == 'result':
            text = 'not implemented'
        elif self.options.target == 'encoding':
            text = f'target option of copy2clipboard ModelReprPlugin is not valid: {repr(self.options.target)}.'
        else:
            text = 'target option of copy2clipboard ModelReprPlugin is not valid: {self.options.target}'
        bid = f'{idx}-{self.options.button_id}' if self.options.button_id else idx
        return self.__create_button(bid, text)

    def on_header(self, **kwargs):
        if self.options.target == 'encoding':
            text = kargs.get('encoding', 'no encoding provided to copy2clipboard.on_header method')
        else:
            text = 'target option of copy2clipboard ModelReprPlugin is not valid: {self.options.target}'
        bid = f'{idx}-{self.options.button_id}' if self.options.button_id else idx
        return self.__create_button(bid, text)

    def on_footer(self):
        if self.options.target == 'encoding':
            text = kargs.get('encoding', 'no encoding provided to copy2clipboard.on_header method')
        else:
            text = 'target option of copy2clipboard ModelReprPlugin is not valid: {self.options.target}'
        bid = f'{idx}-{self.options.button_id}' if self.options.button_id else idx
        return self.__create_button(bid, text)


    def __create_button(self, bid, text):
        return f"""<br/><button id="copybutton-{bid}" onclick='copyTextToClipboard("copybutton-{bid}", "{text}", "{self.options.label_copied}", {self.options.label_copied_duration})' >{self.options.label}</button><br/>"""
