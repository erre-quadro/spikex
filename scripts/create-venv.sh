python3 -m pip install -U --no-cache-dir virtualenv
virtualenv .venv && . .venv/bin/activate
pip install --no-cache-dir cython
pip install --no-cache-dir -r requirements-dev.txt -r requirements.txt
python -m spikex download-wikigraph simplewiki_core