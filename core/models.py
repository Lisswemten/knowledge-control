from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Профиль пользователя с ролью и дополнительной информацией."""

    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('hr', 'HR-специалист'),
        ('manager', 'Руководитель'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee',
        verbose_name='Роль'
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Отдел'
    )
    position = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Должность'
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Телефон'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Аватар'
    )

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создаёт Profile при создании User."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохраняет Profile при сохранении User."""
    instance.profile.save()


class Category(models.Model):
    """Категория знаний (например, «Техника безопасности»)."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Question(models.Model):
    """Вопрос теста."""

    QUESTION_TYPES = [
        ('single', 'Один ответ'),
        ('multiple', 'Несколько ответов'),
        ('text', 'Развёрнутый ответ'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Категория'
    )
    text = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='single',
        verbose_name='Тип вопроса'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_questions',
        verbose_name='Автор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_question_type_display()}] {self.text[:60]}'


class Answer(models.Model):
    """Вариант ответа на вопрос."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )
    text = models.CharField(
        max_length=500,
        verbose_name='Текст ответа'
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name='Правильный'
    )

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'

    def __str__(self):
        marker = '✓' if self.is_correct else '✗'
        return f'{marker} {self.text[:60]}'


class Test(models.Model):
    """Тест — набор вопросов."""

    title = models.CharField(
        max_length=200,
        verbose_name='Название теста'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='tests',
        verbose_name='Категория'
    )
    questions = models.ManyToManyField(
        Question,
        related_name='tests',
        verbose_name='Вопросы'
    )
    pass_score = models.IntegerField(
        default=70,
        verbose_name='Проходной балл (%)'
    )
    time_limit = models.IntegerField(
        default=20,
        verbose_name='Время на прохождение (минут)'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tests',
        verbose_name='Автор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Assignment(models.Model):
    """Назначение теста сотруднику."""

    STATUS_CHOICES = [
        ('assigned', 'Назначен'),
        ('in_progress', 'В процессе'),
        ('passed', 'Пройден'),
        ('failed', 'Не пройден'),
        ('expired', 'Просрочен'),
    ]

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Тест'
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Сотрудник'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_assignments',
        verbose_name='Кто назначил'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата назначения'
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Срок сдачи'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='assigned',
        verbose_name='Статус'
    )

    class Meta:
        verbose_name = 'Назначение'
        verbose_name_plural = 'Назначения'
        ordering = ['-assigned_at']
        unique_together = ('test', 'employee')  # один тест — одно назначение на сотрудника

    def __str__(self):
        return f'{self.employee.username} → {self.test.title} [{self.get_status_display()}]'


class Attempt(models.Model):
    """Попытка прохождения теста."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Назначение'
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Сотрудник'
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Начало'
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Окончание'
    )
    score = models.IntegerField(
        default=0,
        verbose_name='Верных ответов'
    )
    total = models.IntegerField(
        default=0,
        verbose_name='Всего вопросов'
    )
    percent = models.FloatField(
        default=0.0,
        verbose_name='Процент'
    )
    passed = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Пройден'
    )

    class Meta:
        verbose_name = 'Попытка'
        verbose_name_plural = 'Попытки'
        ordering = ['-started_at']

    def __str__(self):
        return f'Попытка {self.employee.username} — {self.assignment.test.title}'


class AttemptAnswer(models.Model):
    """Ответ сотрудника на конкретный вопрос в попытке."""

    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Попытка'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        verbose_name='Вопрос'
    )
    selected_answers = models.ManyToManyField(
        Answer,
        blank=True,
        related_name='selected_in',
        verbose_name='Выбранные ответы'
    )
    text_answer = models.TextField(
        blank=True,
        verbose_name='Текстовый ответ'
    )
    attached_file = models.FileField(
        upload_to='answers/',
        blank=True,
        null=True,
        verbose_name='Прикреплённый файл'
    )
    is_correct = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Верно'
    )

    class Meta:
        verbose_name = 'Ответ в попытке'
        verbose_name_plural = 'Ответы в попытке'

    def __str__(self):
        return f'{self.question.text[:40]} — {"✓" if self.is_correct else "?"}'

class Message(models.Model):
    """Сообщение в общем чате."""

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Отправитель'
    )
    text = models.TextField(verbose_name='Текст сообщения')
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата отправки'
    )

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.text[:40]}'

class Feedback(models.Model):
    """Сообщение обратной связи от пользователя."""

    name = models.CharField(
        max_length=100,
        verbose_name='Имя'
    )
    email = models.EmailField(
        verbose_name='Email'
    )
    text = models.TextField(
        verbose_name='Сообщение'
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name='Отправлено на email'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Обратная связь'
        verbose_name_plural = 'Обратная связь'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} <{self.email}> — {self.text[:40]}'

class Material(models.Model):
    """Материал для подготовки к тесту."""
    title = models.CharField(
        max_length=200,
        verbose_name='Название'
    )
    file = models.FileField(
        upload_to='materials/',
        verbose_name='Файл'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Категория'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_materials',
        verbose_name='Загрузил'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['-uploaded_at']
    def __str__(self):
        return f'{self.title} ({self.category.name})'

class Post(models.Model):
    """Пост в блоге / новость."""
    title = models.CharField(
        max_length=200,
        verbose_name='Заголовок'
    )
    text = models.TextField(
        verbose_name='Текст'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        verbose_name='Автор'
    )
    is_published = models.BooleanField(
        default=True,
        verbose_name='Опубликовано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    class Meta:
        verbose_name = 'Пост блога'
        verbose_name_plural = 'Блог'
        ordering = ['-created_at']

    def __str__(self):
        return self.title