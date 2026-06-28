.PHONY: install start stop restart update backup restore health logs migrate superuser clean

install:
	./scripts/install.sh

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh

restart:
	./scripts/restart.sh

update:
	./scripts/update.sh

backup:
	./scripts/backup.sh

restore:
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backups/orion_backup_XXX.tar.gz"; exit 1; fi
	./scripts/restore.sh $(FILE)

health:
	./scripts/health.sh

logs:
	./scripts/logs.sh $(SERVICE)

migrate:
	./scripts/migrate.sh

superuser:
	./scripts/createsuperuser.sh

clean:
	docker compose down -v
	@echo "Volumes Docker supprimés."
	@echo "ATTENTION: Les données sont perdues. Restaurer depuis une sauvegarde si nécessaire."
