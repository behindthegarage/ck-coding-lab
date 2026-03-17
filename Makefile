SHELL := /bin/bash

.PHONY: help install dev start stop restart status logs health test lint

help:
	@echo "Club Kinawa Coding Lab local commands"
	@echo
	@echo "  make dev      # install unit if needed, then start local dev server"
	@echo "  make start    # start local dev server"
	@echo "  make stop     # stop local dev server"
	@echo "  make restart  # restart local dev server"
	@echo "  make status   # show service + port status"
	@echo "  make logs     # tail service logs"
	@echo "  make health   # check auth health endpoint"
	@echo "  make test     # run tests"
	@echo "  make lint     # run linters"

install:
	./scripts/dev-server.sh install

dev: start

start:
	./scripts/dev-server.sh start

stop:
	./scripts/dev-server.sh stop

restart:
	./scripts/dev-server.sh restart

status:
	./scripts/dev-server.sh status

logs:
	./scripts/dev-server.sh logs

health:
	@curl -sS http://127.0.0.1:5006/api/auth/health && echo

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh
