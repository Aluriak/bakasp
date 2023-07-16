
import os
from aas import create_aas_app

app = create_aas_app(os.getenv('BAKASP_AAS_CONFIG', 'config.cfg'))
