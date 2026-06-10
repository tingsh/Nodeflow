from django.db import migrations

def convert_default_page_to_homepage(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql' and schema_editor.connection.vendor != 'sqlite':
        return
    
    Page = apps.get_model('wagtailcore', 'Page')
    HomePage = apps.get_model('content', 'HomePage')
    ContentTypeModel = apps.get_model('contenttypes', 'ContentType')
    
    try:
        page = Page.objects.get(id=2)
        homepage_ct = ContentTypeModel.objects.get(app_label='content', model='homepage')
        
        if not HomePage.objects.filter(id=2).exists():
            HomePage.objects.create(
                page_ptr_id=2,
            )
            
            page.content_type = homepage_ct
            page.title = "Nodeflow | AI-Powered Industrial IoT Platform"
            page.slug = "home"
            page.save()
            
    except Exception as e:
        pass

class Migration(migrations.Migration):
    dependencies = [
        ('content', '0004_homepage'),
    ]
    operations = [
        migrations.RunPython(convert_default_page_to_homepage, migrations.RunPython.noop),
    ]
