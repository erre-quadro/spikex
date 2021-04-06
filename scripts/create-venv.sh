python3 -m pip install -U --no-cache-dir virtualenv
virtualenv .venv && . .venv/bin/activate
pip install --no-cache-dir -r requirements-dev.txt -r requirements.txt
wget https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EQhheXcD9KtGpXyoZ9a2zOEBmGIvZXuyFoV1KoYOzgsjLw?Download=1 -O simplewiki_core.tar.gz
pip install simplewiki_core.tar.gz
rm simplewiki_core.tar.gz