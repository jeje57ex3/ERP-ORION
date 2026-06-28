"""Crée le superadmin silencieusement."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_btp.settings')
django.setup()

from django.contrib.auth.models import User

username = 'admin'
email = 'admin@erp.local'
password = 'Admin@2024!'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superadmin créé : {username} / {password}")
else:
    print(f"Superadmin '{username}' existe déjà")
