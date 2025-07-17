# 🧾 Scoring Service

**Scoring** — сервис скоринга.

## 🚀 Возможности

- online_score: скоринг пользователя по данным
- clients_interests: получение интересов пользователей

## 📦 Установка

```bash
git clone https://github.com/NikitaKh/scoring.git
cd scoring
poetry install
```

## ⚙️ Пример запуска

```bash
poetry run python -m scoring.api
```

## 🧪 Тестирование

```bash
poetry run pytest
```

## 🔍 Проверки

```bash
poetry run pre-commit run --all-files
```

## 🛠️ CI

Проект включает GitHub Actions workflow (.github/workflows/main.yml), который запускает:

- black
- isort
- flake8
- pytest

при каждом пуше в main или pull request.
