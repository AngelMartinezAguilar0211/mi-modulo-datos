from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler
from django.db import connection, transaction
from django.db.models import Sum, Count
from django.conf import settings
import time
import os
import threading
import duckdb

from transactions.models import Transaction
from transactions.serializers import TransactionSerializer
from transactions.cache import cache

# Global active connection / request tracker
_active_requests = 0
_active_requests_lock = threading.Lock()

# Server startup time
_start_time = time.time()

# Thread-safe DuckDB connection singleton
_duckdb_conn = None
_duckdb_lock = threading.Lock()


def get_duckdb_cursor():
    global _duckdb_conn
    if _duckdb_conn is None:
        with _duckdb_lock:
            if _duckdb_conn is None:
                # Resolve paths relative to settings
                parquet_path = os.getenv(
                    "PARQUET_FILE_PATH",
                    str(settings.BASE_DIR.parent / "data" / "test_1m_snappy.parquet")
                )
                _duckdb_conn = duckdb.connect(database=":memory:", read_only=False)
                _duckdb_conn.execute(f"CREATE OR REPLACE VIEW transactions_view AS SELECT * FROM '{parquet_path}';")
    return _duckdb_conn.cursor()


# Custom exception handler to translate DRF ValidationErrors (400) to HTTP 422
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if isinstance(exc, ValidationError):
        if response is not None:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            response.data = {"detail": response.data}
    return response


# Helper context manager to track active connections
class ActiveRequestTracker:
    def __enter__(self):
        global _active_requests
        with _active_requests_lock:
            _active_requests += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _active_requests
        with _active_requests_lock:
            _active_requests -= 1


# --- Endpoints ---

# 1. GET /health
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    with ActiveRequestTracker():
        uptime_seconds = time.time() - _start_time
        metrics = cache.metrics

        sqlite_ok = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            sqlite_ok = True
        except Exception:
            pass

        duckdb_ok = False
        try:
            cursor = get_duckdb_cursor()
            cursor.execute("SELECT 1;")
            duckdb_ok = True
        except Exception:
            pass

        return Response({
            "status": "healthy" if (sqlite_ok and duckdb_ok) else "degraded",
            "connections_active": _active_requests,
            "cache_hit_rate": metrics["hit_rate"],
            "cache_hits": metrics["hits"],
            "cache_misses": metrics["misses"],
            "uptime_seconds": round(uptime_seconds, 2),
            "sqlite_connected": sqlite_ok,
            "duckdb_connected": duckdb_ok
        })


# 2. GET /analytics/summary
@api_view(['GET'])
@permission_classes([AllowAny])
def analytics_summary(request):
    with ActiveRequestTracker():
        cache_key = "analytics_summary"
        cached_res = cache.get(cache_key)
        if cached_res:
            return Response(cached_res)

        try:
            cursor = get_duckdb_cursor()

            # Global metrics
            cursor.execute("SELECT COUNT(*), SUM(amount), AVG(amount) FROM transactions_view;")
            total_cnt, total_amt, avg_amt = cursor.fetchone()

            # Country breakdown
            cursor.execute("SELECT country_code, COUNT(*), SUM(amount) FROM transactions_view GROUP BY country_code;")
            country_rows = cursor.fetchall()
            breakdown_by_country = {
                row[0]: {"count": row[1], "amount": float(row[2])} for row in country_rows
            }

            # Category breakdown
            cursor.execute("SELECT category, COUNT(*), SUM(amount) FROM transactions_view GROUP BY category;")
            category_rows = cursor.fetchall()
            breakdown_by_category = {
                row[0]: {"count": row[1], "amount": float(row[2])} for row in category_rows
            }

            result = {
                "total_count": int(total_cnt) if total_cnt is not None else 0,
                "total_amount": float(total_amt) if total_amt is not None else 0.0,
                "avg_amount": float(avg_amt) if avg_amt is not None else 0.0,
                "breakdown_by_country": breakdown_by_country,
                "breakdown_by_category": breakdown_by_category
            }

            # Cache the result for 60 seconds
            cache_ttl = int(os.getenv("CACHE_TTL", "60"))
            cache.set(cache_key, result, cache_ttl)
            return Response(result)
        except Exception as e:
            return Response(
                {"detail": f"DuckDB analytical query failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# 3. GET /analytics/top-merchants
@api_view(['GET'])
@permission_classes([AllowAny])
def analytics_top_merchants(request):
    with ActiveRequestTracker():
        limit_param = request.query_params.get("limit", "10")
        try:
            limit = int(limit_param)
            if limit < 1:
                raise ValueError()
        except ValueError:
            raise ValidationError({"limit": "Limit must be a positive integer greater than or equal to 1"})

        country = request.query_params.get("country", None)
        if country and len(country) != 2:
            raise ValidationError({"country": "Country must be a 2-character ISO code"})

        country_upper = country.upper() if country else None
        cache_key = f"analytics_top_merchants_limit_{limit}_country_{country_upper}"

        cached_res = cache.get(cache_key)
        if cached_res:
            return Response(cached_res)

        try:
            cursor = get_duckdb_cursor()

            if country_upper:
                cursor.execute(
                    """
                    SELECT merchant_id, SUM(amount) as volume, COUNT(*) as tx_count
                    FROM transactions_view
                    WHERE country_code = ?
                    GROUP BY merchant_id
                    ORDER BY volume DESC
                    LIMIT ?;
                    """,
                    (country_upper, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT merchant_id, SUM(amount) as volume, COUNT(*) as tx_count
                    FROM transactions_view
                    GROUP BY merchant_id
                    ORDER BY volume DESC
                    LIMIT ?;
                    """,
                    (limit,)
                )

            rows = cursor.fetchall()
            result = [
                {
                    "merchant_id": int(row[0]),
                    "volume": float(row[1]),
                    "transaction_count": int(row[2])
                }
                for row in rows
            ]

            cache_ttl = int(os.getenv("CACHE_TTL", "60"))
            cache.set(cache_key, result, cache_ttl)
            return Response(result)
        except Exception as e:
            return Response(
                {"detail": f"DuckDB analytical query failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# 4. GET /users/{user_id}/transactions
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_transactions(request, user_id):
    with ActiveRequestTracker():
        if not (1 <= user_id <= 50000):
            raise ValidationError({"user_id": "User ID must be between 1 and 50000"})

        page_param = request.query_params.get("page", "1")
        page_size_param = request.query_params.get("page_size", "20")

        try:
            page = int(page_param)
            if page < 1:
                raise ValueError()
        except ValueError:
            return Response({"detail": "Page must be a positive integer >= 1."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            page_size = int(page_size_param)
            if not (1 <= page_size <= 100):
                raise ValueError()
        except ValueError:
            return Response({"detail": "Page size must be between 1 and 100."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx_queryset = Transaction.objects.filter(user_id=user_id).order_by('-timestamp')
            total_records = tx_queryset.count()

            if total_records == 0:
                return Response(
                    {"detail": f"User {user_id} not found or has no transactions."},
                    status=status.HTTP_404_NOT_FOUND
                )

            total_pages = (total_records + page_size - 1) // page_size

            if page > total_pages:
                return Response(
                    {"detail": f"Page {page} is out of range. Total pages: {total_pages}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            offset = (page - 1) * page_size
            page_txs = tx_queryset[offset:offset + page_size]
            serializer = TransactionSerializer(page_txs, many=True)

            return Response({
                "user_id": user_id,
                "page": page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": total_pages,
                "transactions": serializer.data
            })
        except Exception as e:
            return Response(
                {"detail": f"SQLite query failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# 5. GET /users/{user_id}/stats
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_stats(request, user_id):
    with ActiveRequestTracker():
        if not (1 <= user_id <= 50000):
            raise ValidationError({"user_id": "User ID must be between 1 and 50000"})

        try:
            user_txs = Transaction.objects.filter(user_id=user_id)
            agg = user_txs.aggregate(cnt=Count('transaction_id'), total_amt=Sum('amount'))
            cnt = agg['cnt']
            total_amt = agg['total_amt']

            if cnt == 0 or cnt is None:
                return Response(
                    {"detail": f"User {user_id} not found or has no transactions."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Most frequent category
            cat_query = user_txs.values('category').annotate(freq=Count('category')).order_by('-freq', 'category')[:1]
            most_frequent_category = cat_query[0]['category'] if cat_query else "N/A"

            # Primary country code
            country_query = user_txs.values('country_code').annotate(freq=Count('country_code')).order_by('-freq', 'country_code')[:1]
            country_code = country_query[0]['country_code'] if country_query else "N/A"

            return Response({
                "user_id": user_id,
                "total_amount": float(total_amt) if total_amt is not None else 0.0,
                "transaction_count": int(cnt),
                "most_frequent_category": most_frequent_category,
                "country_code": country_code
            })
        except Exception as e:
            return Response(
                {"detail": f"SQLite query failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# 6. POST /transactions/batch
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transactions_batch(request):
    with ActiveRequestTracker():
        batch = request.data
        if not isinstance(batch, list):
            raise ValidationError("Expected a list of transactions.")

        if len(batch) > 500:
            return Response(
                {"detail": "Batch size exceeds maximum limit of 500 transactions."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not batch:
            return Response(
                {"detail": "Empty transaction batch."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # DRF list-level validation
        serializer = TransactionSerializer(data=batch, many=True)
        serializer.is_valid(raise_exception=True)

        # Deduplicate batch in-memory based on transaction_id (keeping the last occurrence)
        seen = {}
        for tx_data in serializer.validated_data:
            seen[tx_data['transaction_id']] = tx_data
        unique_txs = list(seen.values())

        try:
            with transaction.atomic():
                for tx_data in unique_txs:
                    Transaction.objects.update_or_create(
                        transaction_id=tx_data['transaction_id'],
                        defaults={
                            'timestamp': tx_data['timestamp'],
                            'user_id': tx_data['user_id'],
                            'merchant_id': tx_data['merchant_id'],
                            'amount': tx_data['amount'],
                            'category': tx_data['category'],
                            'country_code': tx_data['country_code'],
                            'status': tx_data['status']
                        }
                    )
            return Response({
                "status": "success",
                "received_records": len(batch),
                "inserted_records": len(unique_txs)
            })
        except Exception as e:
            return Response(
                {"detail": f"SQLite transaction failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
