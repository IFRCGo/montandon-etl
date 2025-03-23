#!/bin/bash -e

wait-for-it "$DB_HOST:$DB_PORT"

./manage.py run_celery_dev
