## Getting started

- Clone this repository: git@github.com:IFRCGo/montandon-etl.github
- Go the directory where manage.py exists.
- Create a .env file and copy all environment variable from sample.env.
- Set your own environment variables in .env file.
- Buiid docker using this command:
    ```bash
       docker compose up --build -d
    ```
- Run migration using this command:
    ```bash
       docker-compose exec web python manage.py migrate
    ```
- Command to import GDACS data.
    ```bash
       docker-compose exec web python manage.py import_gdacs_data
    ```
- To view the imported data in the admin panel you need to create yourself as a superuser:
    ```bash
       docker-compose exec web python manage.py createsuperuser
    ```
    Fill up the form for creating super user.
- Once user is created, go the browser and request the link localhost:8000/admin/ to view the data in Extraction data table.
- To go to graphql server go to: localhost:8000/graphql
