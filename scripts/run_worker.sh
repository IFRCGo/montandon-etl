#!/bin/bash -x

celery -A main worker --loglevel=info
