# Generated by Django 4.2.1 on 2023-07-18 00:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0117_pageview_auction_pageview_counter_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lot',
            name='reference_link',
            field=models.URLField(blank=True, help_text='Enter a webpage that has additional information about this lot', null=True),
        ),
        migrations.AlterField(
            model_name='pageview',
            name='source',
            field=models.CharField(blank=True, default='', max_length=200, null=True),
        ),
    ]