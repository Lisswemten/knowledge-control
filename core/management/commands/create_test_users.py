from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Profile

class Command(BaseCommand):
    help = 'Создание тестовых пользователей для демонстрации'
    def handle(self, *args, **kwargs):
        users_data = [
            {
                'username': 'ivanov',
                'password': 'employee123',
                'first_name': 'Иван',
                'last_name': 'Иванов',
                'email': 'ivanov@example.com',
                'role': 'employee',
                'department': 'Продажи',
                'position': 'Менеджер',
                'phone': '+79991112233',
            },
            {
                'username': 'petrova',
                'password': 'hr123456',
                'first_name': 'Анна',
                'last_name': 'Петрова',
                'email': 'petrova@example.com',
                'role': 'hr',
                'department': 'HR-отдел',
                'position': 'Методист',
                'phone': '+79994445566',
            },
            {
                'username': 'sidorov',
                'password': 'manager123',
                'first_name': 'Пётр',
                'last_name': 'Сидоров',
                'email': 'sidorov@example.com',
                'role': 'manager',
                'department': 'Управление',
                'position': 'Начальник отдела',
                'phone': '+79997778899',
            },
        ]
        for data in users_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'email': data['email'],
                }
            )
            if created:
                user.set_password(data['password'])
                user.save()
                # Profile создаётся сигналом, но обновим поля
                profile = user.profile
                profile.role = data['role']
                profile.department = data['department']
                profile.position = data['position']
                profile.phone = data['phone']
                profile.save()
                self.stdout.write(self.style.SUCCESS(f'Создан: {data["username"]} ({data["role"]})'))
            else:
                self.stdout.write(self.style.WARNING(f'Уже существует: {data["username"]}'))