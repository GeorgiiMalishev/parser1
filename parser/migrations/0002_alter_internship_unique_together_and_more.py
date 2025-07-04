# Generated by Django 5.1.2 on 2025-04-20 06:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='internship',
            name='content_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='Хеш содержимого'),
        ),
        migrations.AddField(
            model_name='internship',
            name='duration',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Длительность стажировки'),
        ),
        migrations.AddField(
            model_name='internship',
            name='employment_type',
            field=models.CharField(blank=True, choices=[('remote', 'Удаленно'), ('office', 'Очно'), ('hybrid', 'Гибридный'), ('full_time', 'Полный день'), ('part_time', 'Неполный день'), ('flexible', 'Гибкий график')], max_length=20, null=True, verbose_name='Тип занятости'),
        ),
        migrations.AddField(
            model_name='internship',
            name='external_id',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Идентификатор стажировки'),
        ),
        migrations.AddField(
            model_name='internship',
            name='salary',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Заработная плата'),
        ),
        migrations.AddField(
            model_name='internship',
            name='selection_end_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата окончания отбора'),
        ),
        migrations.AddField(
            model_name='internship',
            name='selection_start_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата начала отбора'),
        ),
        migrations.AddField(
            model_name='internship',
            name='title',
            field=models.CharField(default='position', max_length=255, verbose_name='Название стажировки'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='internship',
            name='end_date',
        ),
        migrations.RemoveField(
            model_name='internship',
            name='format',
        ),
        migrations.RemoveField(
            model_name='internship',
            name='start_date',
        ),
    ]
