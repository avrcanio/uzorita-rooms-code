# Shared Redis (infra-redis)

**Last updated:** 2026-05-16  
**Status:** Active

Zajednički Redis za Celery brokere na Docker mreži `hetzner_net`.

## Stack

- Compose: `/opt/stacks/redis/docker-compose.yml`
- Kontejner: `infra-redis`
- Host port (lokalni alati): `127.0.0.1:6379`
- Docker hostname: `infra-redis:6379`

## DB indeksi

| DB | Potrošač |
|----|----------|
| `0` | Mozart Celery |
| `1` | Uzorita Celery |

## Operativa

```bash
# Podizanje
docker compose -f /opt/stacks/redis/docker-compose.yml up -d

# Health
docker exec infra-redis redis-cli ping

# Logovi
docker logs -f infra-redis
```

## Ovisni stackovi

- Uzorita: `CELERY_BROKER_URL=redis://infra-redis:6379/1`
- Mozart: `CELERY_BROKER_URL=redis://infra-redis:6379/0`

Nakon migracije s lokalnog `mozzart-redis`, stari kontejner se može ukloniti:

```bash
docker stop mozzart-redis 2>/dev/null; docker rm mozzart-redis 2>/dev/null
```
