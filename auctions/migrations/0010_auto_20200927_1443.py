# Generated by Django 3.1.1 on 2020-09-27 14:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0009_auction_pickup_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auction',
            name='alternate_pickup_location',
            field=models.CharField(blank=True, max_length=2000, null=True),
        ),
        migrations.AlterField(
            model_name='auction',
            name='pickup_location',
            field=models.CharField(help_text='Find the location on Google maps, click Menu>Share or Embed Map and paste the embed link here', max_length=2000),
        ),
    ]
