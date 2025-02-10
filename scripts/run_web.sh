#! /bin/bash -x

# /code/scripts/ -> /code/
ROOT_DIR="$(dirname $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd ))"
cd $ROOT_DIR

wait-for-it $DB_HOST:$DB_PORT

uwsgi --ini ./main/uwsgi.ini  # Start uwsgi server
