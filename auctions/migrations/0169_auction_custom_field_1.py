# Generated by Django 5.1.1 on 2025-03-01 16:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0168_auction_allow_bulk_adding_lots_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="auction",
            name="custom_field_1",
            field=models.CharField(
                choices=[("disable", "Off"), ("allow", "Optional"), ("required", "Required for all lots")],
                default="disable",
                help_text="Additional information on the label such as notes, scientific name, collection location...",
                max_length=20,
                verbose_name="Custom field for lots",
            ),
        ),
    ]
