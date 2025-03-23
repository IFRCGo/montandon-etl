#!/bin/bash -e

wait-for-it "$DB_HOST:$DB_PORT"

./manage.py runserver 0.0.0.0:8000
