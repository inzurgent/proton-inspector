import os
import runpy
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
if '--self-test' in sys.argv:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    runpy.run_path(str(root/'packaging'/'smoke_test.py'), run_name='__main__')
else:
    runpy.run_path(str(root/'app.py'), run_name='__main__')
