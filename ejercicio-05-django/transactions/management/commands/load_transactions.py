import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
import pyarrow.parquet as pq
from transactions.models import Transaction


class Command(BaseCommand):
    help = 'Loads transaction data from a Parquet file in chunks using the Django ORM.'

    def handle(self, *args, **options):
        # Resolve parquet path
        parquet_path = os.getenv(
            "PARQUET_FILE_PATH",
            str(settings.BASE_DIR.parent / "data" / "test_1m_snappy.parquet")
        )

        self.stdout.write(self.style.NOTICE(f"Loading data from Parquet file: {parquet_path}"))

        if not os.path.exists(parquet_path):
            self.stdout.write(self.style.ERROR(f"Parquet file not found at {parquet_path}"))
            return

        try:
            pf = pq.ParquetFile(parquet_path)
            total_inserted = 0
            chunk_size = 10000

            # Read and ingest in row groups to save memory
            for i in range(pf.num_row_groups):
                table = pf.read_row_group(i)
                df = table.to_pandas()

                # Ensure timestamps are timezone-aware to prevent Django RuntimeWarnings
                if df['timestamp'].dt.tz is None:
                    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

                # Ingest this pandas dataframe in chunks of chunk_size using ORM
                records = []
                for row in df.itertuples(index=False):
                    records.append(
                        Transaction(
                            transaction_id=str(row.transaction_id),
                            timestamp=row.timestamp,
                            user_id=int(row.user_id),
                            merchant_id=int(row.merchant_id),
                            amount=float(row.amount),
                            category=str(row.category),
                            country_code=str(row.country_code),
                            status=str(row.status)
                        )
                    )

                    if len(records) >= chunk_size:
                        with transaction.atomic():
                            Transaction.objects.bulk_create(records, ignore_conflicts=True)
                        total_inserted += len(records)
                        self.stdout.write(f"Ingested {total_inserted} records...")
                        records = []

                # Ingest remaining records for this row group
                if records:
                    with transaction.atomic():
                        Transaction.objects.bulk_create(records, ignore_conflicts=True)
                    total_inserted += len(records)
                    self.stdout.write(f"Ingested {total_inserted} records...")

            self.stdout.write(self.style.SUCCESS(
                f"Successfully loaded transactions dataset! Ingested {total_inserted} total records."
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during ingestion: {e}"))
