from datetime import datetime
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a timestamped SQLite database backup and optionally prune old backups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="backups",
            help="Directory to store backup files (default: backups).",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=20,
            help="How many latest backups to keep (default: 20). Set 0 to keep all.",
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            raise CommandError(f"Database file not found: {db_path}")

        output_dir = Path(options["output_dir"])
        if not output_dir.is_absolute():
            output_dir = Path(settings.BASE_DIR) / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = output_dir / f"db_backup_{timestamp}.sqlite3"

        shutil.copy2(db_path, backup_file)
        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_file}"))

        keep = options["keep"]
        if keep > 0:
            backups = sorted(output_dir.glob("db_backup_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
            for stale in backups[keep:]:
                stale.unlink(missing_ok=True)
            if len(backups) > keep:
                self.stdout.write(f"Pruned {len(backups) - keep} old backup(s).")
