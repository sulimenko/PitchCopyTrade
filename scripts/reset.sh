#!/usr/bin/env bash
# Полный сброс: удаляет volumes, образы, приводит к чистому состоянию
set -e
docker compose down -v --remove-orphans
docker compose build --no-cache
echo "Сброс завершён. Запустите: docker compose up"
