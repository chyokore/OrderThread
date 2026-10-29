"""Launch the canonical app with its existing configuration and history."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent / 'OrderThread' / 'app.py'), run_name='__main__')
