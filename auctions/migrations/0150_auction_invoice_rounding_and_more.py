# Generated by Django 5.1 on 2024-10-05 13:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0149_alter_userdata_email_me_when_people_comment_on_my_lots_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="auction",
            name="invoice_rounding",
            field=models.BooleanField(
                default=True,
                help_text="Round invoice totals to whole dollar amounts.  Check if you plan to accept cash payments.",
            ),
        ),
        migrations.AlterField(
            model_name="auction",
            name="allow_bidding_on_lots",
            field=models.BooleanField(default=True, verbose_name="Allow online bidding"),
        ),
    ]
