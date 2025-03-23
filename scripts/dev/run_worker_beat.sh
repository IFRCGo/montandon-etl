#!/bin/bash -e

wait-for-it "$DB_HOST:$DB_PORT"

celery -A main beat -l info
