# Generated by Django 5.1.1 on 2024-11-13 15:53

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0161_alter_auction_reprint_reminder_sent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auction",
            name="buy_now",
            field=models.CharField(
                choices=[("disable", "Don't allow"), ("allow", "Allow"), ("required", "Required for all lots")],
                default="allow",
                help_text="Allow lots to be sold without bidding, for a user-specified price.",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="auction",
            name="summernote_description",
            field=models.CharField(blank=True, default="", max_length=10000, verbose_name="Rules"),
        ),
    ]
