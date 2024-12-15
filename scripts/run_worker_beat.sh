#!/bin/bash -x

celery -A main beat --loglevel=info
