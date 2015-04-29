web: gunicorn web_job:app --log-file=-
cron: python pycron.py
#web_cron: gunicorn web_job:app --log-file=- & python pycron.py
#web_ssl: gunicorn --certfile=cert/ssl.cert --keyfile=cert/ssl.key web_job:app --log-file=- -b 0.0.0.0:443
web_ssl: gunicorn --certfile=cert/ssl.cert --keyfile=cert/ssl.key web_job:app --log-file=- -b 0.0.0.0:443
