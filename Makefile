PYTHON := uv run
DOCKER := docker

all: run

run:
	$(PYTHON) manage.py runserver

migrate:
	$(PYTHON) manage.py migrate

up:
	$(DOCKER) compose up -d

down:
	$(DOCKER) compose down --remove-orphans

.PHONY: run migrate up
