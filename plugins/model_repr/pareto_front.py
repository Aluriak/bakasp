
from model_repr import ModelReprPlugin

import io
import plotly
from plotly import express


def pareto_of(scored_models):
    all_scores = set(s for s, m in scored_models)

    def is_worse(sa, sb):
        "True if sa is worse than sb"
        return all(a <= b for a, b in zip(sa, sb)) and any(a < b for a, b in zip(sa, sb))

    unwanted = set()
    for score in all_scores:
        if any(is_worse(score, other) for other in all_scores):
            unwanted.add(score)

    accepted = all_scores - unwanted
    yield from ((s, m) for s, m in scored_models if s in accepted)


class ParetoFront(ModelReprPlugin):
    """Generate and embed a plotly scatter plot.

    """
    OPTIONS = {
        "kind": 'pareto front',
        "x": 'metric_x',
        "y": 'metric_y',
        "title": "Pareto front of solutions according to {x_label} and {y_label} among {optimal_models_count}",
        "x_label": "score X",
        "y_label": "score Y",
        "place": "footer",
        "width": 600,
        "height": 400,
        "model optimality flag": "<u>OPTIMAL</u><br/><br/>",
    }

    def init(self):
        self.all_scored_models = []
        self.optimal_models = None

    def plot_scatter_html(self):
        x, y, uid = zip(*([*s, m.uid] for s, m in self.optimal_models.items()))
        p = express.scatter(
            {'x': x, 'y': y, 'uid': uid}, x='x', y='y',
            title=self.options.title.format(x_label=self.options.x_label, y_label=self.options.y_label, optimal_models_count=len(x)),
            labels={'x': self.options.x_label, 'y': self.options.y_label},
            text='uid',
            width=self.options.width,
            height=self.options.height,
        )
        p.update_traces(textposition='top center')
        with io.StringIO() as out:
            p.write_html(out, auto_open=False, include_plotlyjs='cdn', full_html=False)
            return out.getvalue()

    def get_model_score(self, model: object):
        return (
            int(next((args[0] for pred, args in model.atoms if pred == self.options.x and len(args)==1), 0)),
            int(next((args[0] for pred, args in model.atoms if pred == self.options.y and len(args)==1), 0))
        )

    def on_footer(self, models: tuple, **kwargs):
        if self.optimal_models is None:
            self.optimal_models = dict(pareto_of([(self.get_model_score(model), model) for model in models]))
        if self.options.place.lower() == 'footer':
            return self.plot_scatter_html()

    def on_header(self, models: tuple, **kwargs):
        if self.optimal_models is None:
            self.optimal_models = dict(pareto_of([(self.get_model_score(model), model) for model in models]))
        if self.options.place.lower() == 'header':
            return self.plot_scatter_html()

    def on_model(self, idx: int, uid: str, model: object):
        "We expect that function to be called after creation of footer and headers"
        if uid in (m.uid for m in self.optimal_models.values()):
            return self.options.model_optimality_flag or ''
