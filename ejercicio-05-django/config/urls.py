from django.contrib import admin
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from transactions.views import (
    health_check,
    analytics_summary,
    analytics_top_merchants,
    user_transactions,
    user_stats,
    transactions_batch,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-token-auth/', obtain_auth_token, name='api_token_auth'),
    path('health', health_check, name='health_check'),
    path('analytics/summary', analytics_summary, name='analytics_summary'),
    path('analytics/top-merchants', analytics_top_merchants, name='analytics_top_merchants'),
    path('users/<int:user_id>/transactions', user_transactions, name='user_transactions'),
    path('users/<int:user_id>/stats', user_stats, name='user_stats'),
    path('transactions/batch', transactions_batch, name='transactions_batch'),
]
