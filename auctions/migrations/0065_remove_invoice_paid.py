# Generated by Django 3.1.4 on 2021-01-17 19:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0064_auto_20210117_1401'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invoice',
            name='paid',
        ),
    ]
