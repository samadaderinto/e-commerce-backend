from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product", "0013_alter_product_category")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.CharField(
                choices=[
                    ('fishing', 'fishing'),
                    ('sports', 'sports'),
                    ('electronics', 'electronics'),
                    ('phones', 'phones'),
                    ('games', 'games'),
                    ('tablets', 'tablets'),
                    ('outwear', 'outwear'),
                    ('pets', 'pets'),
                    ('toys', 'toys'),
                    ('computing', 'computing'),
                    ('lingerie', 'lingerie'),
                    ('books', 'books'),
                    ('beverages', 'beverages'),
                    ('kids', 'Kids & baby'),
                    ('home', 'Home & living'),
                    ('kitchen', 'Kitchen & dining'),
                    ('beauty', 'Beauty & personal care'),
                    ('health', 'Health & wellness'),
                    ('garden', 'Garden & tools'),
                    ('automotive', 'Automotive'),
                    ('jewelry', 'Jewelry & watches'),
                    ('software', 'Software & apps'),
                    ('courses', 'Courses & learning'),
                    ('templates', 'Templates & planners'),
                    ('design_assets', 'Design assets'),
                    ('photo_video', 'Photos & video'),
                    ('music_audio', 'Music & audio'),
                    ('business', 'Business resources'),
                    ('digital_tools', 'Digital tools & presets'),
                ],
                max_length=15,
            ),
        ),
    ]
