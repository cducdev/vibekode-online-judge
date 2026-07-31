# Generated manually for VKOJ hidden subtask support.

import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0226_problemtestcase_batch_scoring'),
    ]

    operations = [
        migrations.AddField(
            model_name='contestparticipation',
            name='score_final',
            field=models.FloatField(db_index=True, default=0, verbose_name='final score'),
        ),
        migrations.AddField(
            model_name='contestparticipation',
            name='cumtime_final',
            field=models.PositiveIntegerField(default=0, verbose_name='final cumulative time'),
        ),
        migrations.AddField(
            model_name='contestparticipation',
            name='format_data_final',
            field=jsonfield.fields.JSONField(
                blank=True, null=True, verbose_name='final contest format specific data',
            ),
        ),
        migrations.AddField(
            model_name='contestproblem',
            name='hidden_subtasks',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Comma-separated subtask numbers to hide in New IOI contests.',
                max_length=255,
                verbose_name='hidden subtasks',
            ),
        ),
    ]
