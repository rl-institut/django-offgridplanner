# Generated by Django 5.1.8 on 2025-04-23 13:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('optimization', '0003_rename_task_id_simulation_task_supply_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='simulation',
            old_name='status',
            new_name='status_grid',
        ),
        migrations.RenameField(
            model_name='simulation',
            old_name='task_grid',
            new_name='token_grid',
        ),
        migrations.RenameField(
            model_name='simulation',
            old_name='task_supply',
            new_name='token_supply',
        ),
        migrations.AddField(
            model_name='simulation',
            name='status_supply',
            field=models.CharField(default='not yet started', max_length=25),
        ),
    ]
