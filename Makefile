.PHONY: run test lint format check-all coverage

# Запуск приложения
run:
	poetry run python -m scoring.api

# Запуск тестов
test:
	poetry run python -m tests.test

# Проверки: mypy + flake8
lint:
	#poetry run mypy scoring/
	poetry run flake8 scoring/ tests/

# Форматирование: black + isort
format:
	poetry run black .
	poetry run isort .

# Проверка форматирования и линтеров
check-all:
	poetry run black . --check
	poetry run isort . --check-only
	poetry run flake8 scoring tests
	#poetry run mypy scoring

# Синхронизация poetry
sync:
	poetry lock && poetry install
