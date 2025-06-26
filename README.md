# Montandon ETL

## Getting Started

Clone this repository:

```bash
git clone git@github.com:IFRCGo/montandon-etl.github
cd montandon-etl
```

Update submodules

```bash
 git submodule update --init --recursive
```

Create an empty .env file.

```bash
touch .env
```

Install python dependencies

```bash
# uv should be installed globally
uv sync
```

### Running

Run container using the following command:

```bash
 docker compose up --build -d
```

Run migration using the following command:

```bash
docker-compose exec web python manage.py migrate
```

Create users to access admin panel using the following command:

```bash
docker-compose exec web python manage.py createsuperuser
```

### Triggering data import from external sources

```bash
# Import from GDACS
 docker-compose exec web python manage.py extract_gdacs_data

# Import from GLIDE
docker-compose exec web python manage.py extract_glide_data

# Import from EMDAT
docker-compose exec web python manage.py extract_glide_data

# Import from IDU
docker-compose exec web python manage.py extract_idu_data

# Import from GIDD
docker-compose exec web python manage.py extract_gidd_data

# Import from GFD
docker-compose exec web python manage.py extract_gfd_data
```

### Using proxies

1. First make sure that there are a set of socks5h or https proxies defined in the env variables.
```bash
EXTRACTION_PROXY_1=socks5h://192.168.83.28:1081
EXTRACTION_PROXY_2=socks5h://192.168.83.28:1082
EXTRACTION_PROXY_3=socks5h://192.168.83.28:1083
EXTRACTION_PROXY_4=socks5h://192.168.83.28:1084
```

2. Pass the REQUESTS_PROXY_TO_USE to each individual workers like REQUESTS_PROXY_TO_USE=EXTRACTION_PROXY_1.The value of REQUESTS_PROXY_TO_USE should point to one of the predefined environment variables (like EXTRACTION_PROXY_1) that holds the actual proxy URL. Inside the application, this is resolved to the actual proxy address used by requests. To run multiple workers with different proxies, simply assign a different value to REQUESTS_PROXY_TO_USE for each worker (e.g., EXTRACTION_PROXY_2, EXTRACTION_PROXY_3, etc.).

3. To use with docker compose locally we can run the worker container with REQUESTS_PROXY_TO_USE
```bash
docker compose run --rm worker bash -c "REQUESTS_PROXY_TO_USE=EXTRACTION_PROXY_4 celery -A main worker -Q usgs-extraction-04 --concurrency=4"
```
To run multiple workers in parallel with different proxies:
```bash
docker compose run --rm worker bash -c "REQUESTS_PROXY_TO_USE=EXTRACTION_PROXY_1 celery -A main worker -Q usgs-extraction-01 --concurrency=4"
docker compose run --rm worker bash -c "REQUESTS_PROXY_TO_USE=EXTRACTION_PROXY_2 celery -A main worker -Q usgs-extraction-02 --concurrency=4"
docker compose run --rm worker bash -c "REQUESTS_PROXY_TO_USE=EXTRACTION_PROXY_3 celery -A main worker -Q usgs-extraction-03 --concurrency=4"
```

4. To run inside the cluster we can configure the workers with individual REQUESTS_PROXY_TO_USE:
```yaml
usgs-extraction-01:
  enabled: true
  replicaCount: 1
  celeryArgs: ["--concurrency", "2", "--max-tasks-per-child", "10", "-Q", "usgs-extraction-01"]
  env:
    REQUESTS_PROXY_TO_USE: EXTRACTION_PROXY_1
usgs-extraction-02:
  enabled: true
  replicaCount: 1
  celeryArgs: ["--concurrency", "2", "--max-tasks-per-child", "10", "-Q", "usgs-extraction-02"]
  env:
    REQUESTS_PROXY_TO_USE: EXTRACTION_PROXY_2
```
