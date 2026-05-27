from rest_framework import serializers
from transactions.models import Transaction
import uuid

CATEGORIES = {"Food", "Travel", "Electronics", "Health", "Entertainment", "Retail", "Transport", "Education", "Services", "Other"}
COUNTRIES = {"MX", "CO", "BR", "AR", "CL", "PE", "EC", "VE", "BO", "PY", "UY", "CR", "GT", "PA", "DO"}
STATUSES = {"completed", "failed", "pending"}


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'timestamp',
            'user_id',
            'merchant_id',
            'amount',
            'category',
            'country_code',
            'status'
        ]

    def validate_transaction_id(self, value):
        try:
            uuid.UUID(str(value))
        except ValueError:
            raise serializers.ValidationError("transaction_id must be a valid UUID4")
        return value

    def validate_user_id(self, value):
        if not (1 <= value <= 50000):
            raise serializers.ValidationError("user_id must be between 1 and 50000")
        return value

    def validate_merchant_id(self, value):
        if not (1 <= value <= 10000):
            raise serializers.ValidationError("merchant_id must be between 1 and 10000")
        return value

    def validate_amount(self, value):
        if not (0.01 <= value <= 5000.00):
            raise serializers.ValidationError("amount must be between 0.01 and 5000.00")
        return value

    def validate_category(self, value):
        if value not in CATEGORIES:
            raise serializers.ValidationError(f"category must be one of {CATEGORIES}")
        return value

    def validate_country_code(self, value):
        if value not in COUNTRIES:
            raise serializers.ValidationError(f"country_code must be one of {COUNTRIES}")
        return value

    def validate_status(self, value):
        if value not in STATUSES:
            raise serializers.ValidationError(f"status must be one of {STATUSES}")
        return value
