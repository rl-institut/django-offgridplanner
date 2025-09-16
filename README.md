# Offgridplanner-Django

This tool is the Django-based implementation of the already existing [Offgridplanner tool](https://github.com/rl-institut/tier_spatial_planning/), which originated from the [PeopleSun](https://reiner-lemoine-institut.de/projekt/peoplesun-optimierung-von-off-grid-energieversorgungssystemen-in-nigeria/) project and was originally written using FastAPI.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

#  Web-Application
The open-source tool originated from the PeopleSuN project and serves the planning of off-grid systems in Nigeria.
The tool aims to perform a spatial optimization of the distribution grid as well as the design of the energy converters
and energy storage.

![Docker Network Diagram](offgridplanner/static/images/results_example.jpg)
## Features
The features of the tool are listed below:
- **Automatic Identification of Buildings from OpenStreetMap:** Utilizes OpenStreetMap data to automatically identify building locations.
- **Spatial Optimization of the Distribution Grid:** Enhances the efficiency of the distribution grid through spatial optimization techniques.
- **Design Optimization of Generation Systems:** Optimizes the design of PV systems, battery systems, inverters, and diesel-engines.
- **Automatic Identification for Individual Solar Home Systems:** Identifies buildings that are more suitably served by individual solar home systems.


## Basic Structure
The application is composed of the following services:
- `django`: the application running behind Gunicorn.
- `postgres`: PostgreSQL database with the application’s data.
- `redis`: Redis instance for caching.
- `traefik`: Traefik reverse proxy with HTTPS on by default.
- `celeryworker`: Dunning a Celery worker process.
- `flower`: To manage and monitor the celery task queue.

## Getting Started Locally
### With Docker Compose
The environment variables for Docker are defined within the `.envs` folder. You also need to define the following variables (for example in a `.env` file):

```
SIM_API_HOST=<offgrid-planner-optimizer-url>
RN_API_HOST=https://www.renewables.ninja/api/
RN_API_TOKEN=<your-renewables-ninja-api-token>
```

You can sign up to [renewables.ninja](https://www.renewables.ninja/register) for free, and get an API token. 
To install the offgridplanner optimizer locally, follow instructions at https://github.com/rl-institut/optimizer-offgridplanner, or point `SIM_API_HOST` to the testing instance at https://optimizer-offgridplanner-app.apps2.rl-institut.de.


To build the container, open a terminal at
the project root and run the following for local development:
```bash
docker compose -f docker-compose.local.yml up -d --build
```
If you want to emulate production environment use `docker-compose.production.yml` instead. For more information please
refer to the [cookiecutter-django documentation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally-docker.html).

### With a local development server
Make sure you have the following installed:
- Python 3.12
- PostgreSQL
- Redis (you may have to install the Windows Subsystem for Linux (WSL) if developing on Windows)
- Mailpit

Then proceed to the next steps.
1. Create a virtual environment using `python=3.12`
2. Activate your virtual environment
3. Create a new postgreSQL database
4. Define your environment variables (you can create a `.env` file at the root level, it will be read by Django)
```
POSTGRES_ENGINE=django.db.backends.postgresql
POSTGRES_DB=<your db name>
POSTGRES_USER=<your username>
POSTGRES_PASSWORD=<your password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
USE_DOCKER=(yes|no)
DJANGO_DEBUG=(True|False)
```
5. Execute the local_setup.sh file (`sh local_setup.sh` / `. local_setup.sh`)
6. Start the redis service with `redis-server` (you will need to use a WSL terminal if developing on Windows)
7. Start the celery worker in a separate terminal with `celery -A config.celery_app worker -l info` (you may have to specify `--pool=solo` if developing on Windows)
8. Start your local mail server in a new terminal with `mailpit`. To view the UI, access http://127.0.0.1:8025/
9. Start the local development server in a new terminal with `python manage.py runserver` :)

For more information on developing locally, refer to the [cookiecutter-django documentation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally.html).

## Settings

For more information about Django [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).
