#! /bin/bash -x

# /code/scripts/ -> /code/
ROOT_DIR="$(dirname $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd ))"
cd $ROOT_DIR

./manage.py wait_for_resources --db

uwsgi --ini ./main/uwsgi.ini  # Start uwsgi server
