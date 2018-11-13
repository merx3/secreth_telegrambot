#!/bin/bash

if [ "$1" == "ci" ]; then
	pytest --ignore=src --junitxml=test-reports/junit.xml --cov=Commands --cov=GamesController --cov=MainController --cov=Boardgamebox --cov=Persistance --cov=Constants --cov-report xml:test-reports/coverage.xml --cov-report html:test-reports/html
else
	pytest -v --ignore=src --cov=Commands --cov=GamesController --cov=MainController --cov=Boardgamebox --cov=Persistance --cov=Constants --cov-report html:test-reports/html --cov-report term
fi
