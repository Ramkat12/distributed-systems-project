.PHONY: build up down clean

build:
	docker compose build

up:
	docker network create net1 2>/dev/null || true
	docker compose up -d

down:
	docker compose down

clean:
	docker compose down --rmi all --volumes --remove-orphans
	docker network rm net1 2>/dev/null || true
