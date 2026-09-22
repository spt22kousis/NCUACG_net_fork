# 把原本寫死在 frontend/src/pages/Works.tsx 的社課列表搬進資料庫，
# 讓 migrate 完之後成果牆左側的列表跟改版前一模一樣。之後的增刪改請走 Django admin。
from django.db import migrations

COURSES = [
    # slug,               name,             color,   order
    ("about",             "關於聲優社課",     "blue",  0),
    ("114-upper",         "114上CM",         "blue",  10),
    ("114-upper-photos",  "114上CM照片",      "blue",  11),
    ("113-lower",         "113下CM",         "green", 20),
    ("113-lower-photos",  "113下CM照片",      "green", 21),
    ("112-lower",         "112下CM",         "blue",  30),
    ("112-lower-photos",  "112下CM照片",      "blue",  31),
]


def seed(apps, schema_editor):
    Course = apps.get_model("club", "Course")
    for slug, name, color, order in COURSES:
        # 已存在就不覆蓋，避免蓋掉幹部在後台改過的名稱或順序
        Course.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "color": color, "order": order, "category": "seiyuu"},
        )


def unseed(apps, schema_editor):
    Course = apps.get_model("club", "Course")
    # 只刪還沒有作品的，避免回滾時連帶刪掉真實作品
    Course.objects.filter(slug__in=[c[0] for c in COURSES], works__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("club", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
