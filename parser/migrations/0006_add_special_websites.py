from django.db import migrations

def add_special_sites(apps, schema_editor):
    Website = apps.get_model('parser', 'Website')
    sites_data = [
        {"name": "HeadHunter", "url": "https://hh.ru/", "is_special": True},
        {"name": "Habr Career", "url": "https://career.habr.com/", "is_special": True},
        {"name": "SuperJob", "url": "https://www.superjob.ru/", "is_special": True},
    ]
    for site_data in sites_data:
        Website.objects.get_or_create(
            name=site_data["name"],
            defaults={'url': site_data["url"], 'is_special': site_data["is_special"]}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('parser', '0005_website_is_special'),
    ]

    operations = [
        migrations.RunPython(add_special_sites),
    ] 