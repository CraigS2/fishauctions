# Generated by Django 3.1.1 on 2020-10-10 18:29

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auctions', '0017_bid_was_high_bid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lot',
            name='banned',
            field=models.BooleanField(default=False, help_text="This lot will be hidden from views, and users won't be able to bid on it.  Banned lots are not charged in invoices."),
        ),
        migrations.CreateModel(
            name='UserIgnoreCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auctions.category')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
