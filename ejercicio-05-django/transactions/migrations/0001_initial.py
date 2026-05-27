from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('transaction_id', models.CharField(max_length=36, primary_key=True, serialize=False)),
                ('timestamp', models.DateTimeField()),
                ('user_id', models.IntegerField()),
                ('merchant_id', models.IntegerField()),
                ('amount', models.FloatField()),
                ('category', models.CharField(max_length=50)),
                ('country_code', models.CharField(max_length=2)),
                ('status', models.CharField(max_length=20)),
            ],
            options={
                'db_table': 'transactions',
                'indexes': [models.Index(fields=['user_id', '-timestamp'], name='idx_user_timestamp'), models.Index(fields=['country_code'], name='idx_country_code')],
            },
        ),
    ]
