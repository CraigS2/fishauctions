# Generated by Django 5.0.8 on 2024-08-22 13:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0141_auctiontos_email_address_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="club",
            name="date_contacted_for_in_person_auctions",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
