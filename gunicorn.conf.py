import os

bind = '0.0.0.0:' + os.getenv('PORT', '10000')
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
threads = 2
timeout = 60
accesslog = '-'
errorlog = '-'
