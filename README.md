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

## Testing

Run tests for ETL sources:

- **In terminal with coverage output:**

```bash
docker compose exec web pytest --cov-report=term --cov=apps apps/etl/tests/sources/*.py -s
```

- **Generate HTML coverage report (saved in `htmlcov/`):**

```bash
docker compose exec web pytest --cov-report=html:htmlcov --cov=apps apps/etl/tests/sources/*.py -s
```
