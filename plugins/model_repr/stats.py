from model_repr import ModelReprPlugin
from collections import Counter

import io
import plotly
from plotly import express


class stats(ModelReprPlugin):
    STAT_FIELDS = 'union', 'intersection', 'counts'
    OPTIONS = {
        "kind": 'stats',
        **{f: True for f in STAT_FIELDS},
        "plot counts": True,
        "title": "barplot of atom counts",
        "width": 0,
        "height": 0,
        "x_label": "{title}",
        "y_label": "number of atoms accross models",
        "include_plotlyjs": 'cdn',
    }

    def render_stats_of(self, models) -> [str]:
        self.compute_union_intersection_and_counts(models)
        for field in stats.STAT_FIELDS:
            if getattr(self.options, field):
                yield from getattr(self, f'get_{field}')(models)


    def on_header(self, models: tuple, **kwargs):
        return '<br/>\n'.join(self.render_stats_of(models))


    def compute_union_intersection_and_counts(self, models):
        models = iter(models)
        first = next(models)
        union, intersection = set(first.atoms), set(first.atoms)
        for model in models:
            union |= set(model.atoms)
            intersection &= set(model.atoms)
        self.__union = frozenset(union)
        self.__intersection = frozenset(intersection)
        self.__counts = Counter(f'{pred}/{len(args)}' for pred, args in self.__union)

    def get_union(self, models):
        yield f"A total of {len(self.__union)} different atoms were generated."
    def get_intersection(self, models):
        yield f"All models have {len(self.__intersection)} atoms in common."
    def get_counts(self, models):
        if self.options.plot_counts:
            uid, cs = zip(*self.__counts.items())
            title = self.options.title
            p = express.bar(
                {'counts': cs, 'atoms': uid, 'uid': uid}, x='atoms', y='counts',
                title=title,
                labels={'x': self.options.y_label.format(title=title), 'y': self.options.y_label},
                # text='uid',
                width=self.options.width,
                height=self.options.height,
            )
            p.update_traces(textposition='auto')
            with io.StringIO() as out:
                p.write_html(out, auto_open=False, include_plotlyjs=self.options.include_plotlyjs, full_html=False)
                yield out.getvalue()
        else:
            yield f"Atom counts: {self.__counts}"
