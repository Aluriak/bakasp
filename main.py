
import glob
from poc import create_app
from utils import create_sorry_app

cfg = next(iter(glob.glob('services/*.json')), None)
app = cfg and create_app(cfg) or create_sorry_app()
