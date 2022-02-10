
import sys
from poc import create_app
from utils import create_sorry_app

app = create_app(sys.argv[1]) or create_sorry_app()
