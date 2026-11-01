from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .forms import EmployeeRegisterForm, ProfileEditForm
from .models import Assignment, Attempt, AttemptAnswer, Answer, Category, Question, Test, Message, Feedback, Material, Post
from django.contrib.auth.models import User
from django.db.models import Count, Avg, Q
from django.http import JsonResponse
from django.conf import settings
from django.core.mail import send_mail

def home(request):
    """Главная страница приложения."""
    return render(request, 'home.html')

def register_view(request):
    """Регистрация нового сотрудника."""
    if request.user.is_authenticated:
        return redirect('profile')
    if request.method == 'POST':
        form = EmployeeRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.first_name}!')
            return redirect('profile')
    else:
        form = EmployeeRegisterForm()
    return render(request, 'register.html', {'form': form})

class CustomLoginView(LoginView):
    """Кастомная страница входа."""
    template_name = 'login.html'
    redirect_authenticated_user = True

def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('home')

@login_required
def profile_view(request):
    """Просмотр и редактирование профиля."""
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён.')
            return redirect('profile')
    else:
        form = ProfileEditForm(instance=request.user.profile)
    return render(request, 'profile.html', {'form': form})

@login_required
def employee_dashboard(request):
    """Личный кабинет сотрудника — список назначенных тестов."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    # Автопереход в expired
    now = timezone.now()
    Assignment.objects.filter(
        employee=request.user,
        deadline__lt=now,
        status__in=['assigned', 'in_progress']
    ).update(status='expired')
    assignments = Assignment.objects.filter(
        employee=request.user
    ).select_related('test', 'test__category').order_by('-assigned_at')
    # Разделяем на активные и завершённые
    active = [a for a in assignments if a.status in ('assigned', 'in_progress')]
    finished = [a for a in assignments if a.status in ('passed', 'failed', 'expired')]
    context = {
        'active_assignments': active,
        'finished_assignments': finished,
    }
    return render(request, 'employee/dashboard.html', context)

@login_required
def employee_history(request):
    """История попыток сотрудника."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    attempts = Attempt.objects.filter(
        employee=request.user
    ).select_related('assignment', 'assignment__test').order_by('-started_at')
    return render(request, 'employee/history.html', {'attempts': attempts})

@login_required
def test_start(request, assignment_id):
    """Страница старта теста — предупреждение перед началом."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    assignment = get_object_or_404(
        Assignment, id=assignment_id, employee=request.user
    )
    # Если уже пройден/просрочен — не пускаем
    if assignment.status in ('passed', 'failed', 'expired'):
        messages.warning(request, 'Этот тест уже завершён.')
        return redirect('employee_dashboard')
    # Проверяем дедлайн
    if assignment.deadline and assignment.deadline < timezone.now():
        assignment.status = 'expired'
        assignment.save()
        messages.error(request, 'Срок прохождения теста истёк.')
        return redirect('employee_dashboard')
    context = {
        'assignment': assignment,
        'test': assignment.test,
        'question_count': assignment.test.questions.count(),
    }
    return render(request, 'employee/test_start.html', context)

@login_required
def test_process(request, assignment_id):
    """Прохождение теста — создаём попытку и показываем вопросы."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    assignment = get_object_or_404(
        Assignment, id=assignment_id, employee=request.user
    )
    # Защита: если уже завершён
    if assignment.status in ('passed', 'failed', 'expired'):
        messages.warning(request, 'Этот тест уже завершён.')
        return redirect('employee_dashboard')
    # Проверяем, есть ли уже открытая попытка
    attempt = Attempt.objects.filter(
        assignment=assignment,
        employee=request.user,
        finished_at__isnull=True
    ).first()
    # Если нет — создаём
    if not attempt:
        attempt = Attempt.objects.create(
            assignment=assignment,
            employee=request.user,
            total=assignment.test.questions.count()
        )
        assignment.status = 'in_progress'
        assignment.save()
    questions = assignment.test.questions.all().prefetch_related('answers')
    context = {
        'assignment': assignment,
        'test': assignment.test,
        'attempt': attempt,
        'questions': questions,
        'time_limit_seconds': assignment.test.time_limit * 60,
    }
    return render(request, 'employee/test_process.html', context)

@login_required
def test_submit(request, assignment_id):
    """Обработка отправки ответов и подсчёт баллов."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    assignment = get_object_or_404(
        Assignment, id=assignment_id, employee=request.user
    )
    if request.method != 'POST':
        return redirect('test_process', assignment_id=assignment_id)
    attempt = Attempt.objects.filter(
        assignment=assignment,
        employee=request.user,
        finished_at__isnull=True
    ).first()
    if not attempt:
        messages.error(request, 'Открытая попытка не найдена.')
        return redirect('employee_dashboard')
    questions = assignment.test.questions.all()
    total_auto = 0
    score = 0
    for q in questions:
        attempt_answer = AttemptAnswer.objects.create(
            attempt=attempt,
            question=q,
        )
        if q.question_type == 'single':
            total_auto += 1
            answer_id = request.POST.get(f'question_{q.id}')
            if answer_id:
                try:
                    answer = Answer.objects.get(id=answer_id, question=q)
                    attempt_answer.selected_answers.add(answer)
                    if answer.is_correct:
                        attempt_answer.is_correct = True
                        score += 1
                    else:
                        attempt_answer.is_correct = False
                except Answer.DoesNotExist:
                    attempt_answer.is_correct = False
            attempt_answer.save()
        elif q.question_type == 'multiple':
            total_auto += 1
            selected_ids = request.POST.getlist(f'question_{q.id}')
            correct_ids = set(
                q.answers.filter(is_correct=True).values_list('id', flat=True)
            )
            selected_set = set()
            for sid in selected_ids:
                try:
                    answer = Answer.objects.get(id=sid, question=q)
                    attempt_answer.selected_answers.add(answer)
                    selected_set.add(int(sid))
                except Answer.DoesNotExist:
                    pass
            if selected_set == correct_ids and correct_ids:
                attempt_answer.is_correct = True
                score += 1
            else:
                attempt_answer.is_correct = False
            attempt_answer.save()
        elif q.question_type == 'text':
            text = request.POST.get(f'text_{q.id}', '').strip()
            attempt_answer.text_answer = text
            file = request.FILES.get(f'file_{q.id}')
            if file:
                attempt_answer.attached_file = file
            attempt_answer.is_correct = None
            attempt_answer.save()
    attempt.finished_at = timezone.now()
    attempt.total = total_auto
    attempt.score = score
    attempt.percent = (score / total_auto * 100) if total_auto > 0 else 0.0
    if total_auto == 0:
        attempt.passed = None
        assignment.status = 'in_progress'
    else:
        attempt.passed = attempt.percent >= assignment.test.pass_score
        assignment.status = 'passed' if attempt.passed else 'failed'
    attempt.save()
    assignment.save()
    return redirect('test_result', attempt_id=attempt.id)

@login_required
def test_result(request, attempt_id):
    """Страница результата."""
    if request.user.profile.role != 'employee':
        messages.error(request, 'Доступ только для сотрудников.')
        return redirect('profile')
    attempt = get_object_or_404(Attempt, id=attempt_id, employee=request.user)
    answers = attempt.answers.select_related('question')
    context = {
        'attempt': attempt,
        'assignment': attempt.assignment,
        'test': attempt.assignment.test,
        'answers': answers,
    }
    return render(request, 'employee/test_result.html', context)

@login_required
def hr_dashboard(request):
    """Главная страница HR-панели."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    context = {
        'categories_count': Category.objects.count(),
        'questions_count': Question.objects.count(),
        'tests_count': Test.objects.count(),
        'assignments_count': Assignment.objects.count(),
        'recent_assignments': Assignment.objects.select_related(
            'employee', 'test'
        ).order_by('-assigned_at')[:5],
        'recent_attempts': Attempt.objects.select_related(
            'employee', 'assignment__test'
        ).order_by('-started_at')[:5],
    }
    return render(request, 'hr/dashboard.html', context)

@login_required
def hr_categories(request):
    """Список категорий."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    categories = Category.objects.all().order_by('name')
    return render(request, 'hr/categories.html', {'categories': categories})

@login_required
def hr_category_add(request):
    """Добавление категории."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Название не может быть пустым.')
        elif Category.objects.filter(name=name).exists():
            messages.error(request, 'Категория с таким названием уже существует.')
        else:
            Category.objects.create(name=name, description=description)
            messages.success(request, f'Категория «{name}» добавлена.')
            return redirect('hr_categories')
    return render(request, 'hr/category_form.html', {'action': 'add'})

@login_required
def hr_category_edit(request, category_id):
    """Редактирование категории."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Название не может быть пустым.')
        elif Category.objects.filter(name=name).exclude(id=category.id).exists():
            messages.error(request, 'Категория с таким названием уже существует.')
        else:
            category.name = name
            category.description = description
            category.save()
            messages.success(request, 'Категория обновлена.')
            return redirect('hr_categories')
    return render(request, 'hr/category_form.html', {
        'action': 'edit',
        'category': category,
    })

@login_required
def hr_category_delete(request, category_id):
    """Удаление категории (с подтверждением)."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        if category.questions.exists():
            messages.error(request, 'Нельзя удалить: к категории привязаны вопросы.')
            return redirect('hr_categories')
        name = category.name
        category.delete()
        messages.success(request, f'Категория «{name}» удалена.')
        return redirect('hr_categories')
    return render(request, 'hr/category_delete.html', {'category': category})

@login_required
def hr_questions(request):
    """Список вопросов с фильтром по категории."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    category_id = request.GET.get('category')
    questions = Question.objects.select_related('category').prefetch_related('answers')
    if category_id:
        questions = questions.filter(category_id=category_id)
    questions = questions.order_by('-created_at')
    context = {
        'questions': questions,
        'categories': Category.objects.all().order_by('name'),
        'selected_category': category_id,
    }
    return render(request, 'hr/questions.html', context)

@login_required
def hr_question_add(request):
    """Добавление вопроса с вариантами ответов."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    if request.method == 'POST':
        category_id = request.POST.get('category')
        text = request.POST.get('text', '').strip()
        question_type = request.POST.get('question_type', 'single')
        errors = []
        if not category_id:
            errors.append('Выберите категорию.')
        if not text:
            errors.append('Введите текст вопроса.')
        # Обработка вариантов ответа
        answer_texts = request.POST.getlist('answer_text[]')
        # Чекбоксы правильных ответов приходят с индексами
        correct_indexes = set()
        for key in request.POST:
            if key.startswith('answer_correct_'):
                correct_indexes.add(int(key.replace('answer_correct_', '')))
        if question_type in ('single', 'multiple'):
            non_empty = [(i, t.strip()) for i, t in enumerate(answer_texts) if t.strip()]
            if len(non_empty) < 2:
                errors.append('Нужно минимум 2 варианта ответа.')
            correct_count = sum(1 for i, _ in non_empty if i in correct_indexes)
            if correct_count == 0:
                errors.append('Отметьте хотя бы один правильный ответ.')
            if question_type == 'single' and correct_count > 1:
                errors.append('Для типа «Один ответ» правильный вариант должен быть только один.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'hr/question_form.html', {
                'action': 'add',
                'categories': Category.objects.all().order_by('name'),
                'form_data': request.POST,
            })
        # Создаём вопрос
        question = Question.objects.create(
            category_id=category_id,
            text=text,
            question_type=question_type,
            created_by=request.user,
        )
        # Создаём ответы
        if question_type in ('single', 'multiple'):
            for i, ans_text in enumerate(answer_texts):
                ans_text = ans_text.strip()
                if ans_text:
                    Answer.objects.create(
                        question=question,
                        text=ans_text,
                        is_correct=(i in correct_indexes),
                    )
        messages.success(request, 'Вопрос добавлен.')
        return redirect('hr_questions')
    # GET
    return render(request, 'hr/question_form.html', {
        'action': 'add',
        'categories': Category.objects.all().order_by('name'),
    })

@login_required
def hr_question_edit(request, question_id):
    """Редактирование вопроса и его вариантов."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    question = get_object_or_404(Question, id=question_id)
    if request.method == 'POST':
        category_id = request.POST.get('category')
        text = request.POST.get('text', '').strip()
        question_type = request.POST.get('question_type', 'single')
        errors = []
        if not category_id:
            errors.append('Выберите категорию.')
        if not text:
            errors.append('Введите текст вопроса.')
        answer_texts = request.POST.getlist('answer_text[]')
        correct_indexes = set()
        for key in request.POST:
            if key.startswith('answer_correct_'):
                correct_indexes.add(int(key.replace('answer_correct_', '')))
        if question_type in ('single', 'multiple'):
            non_empty = [(i, t.strip()) for i, t in enumerate(answer_texts) if t.strip()]
            if len(non_empty) < 2:
                errors.append('Нужно минимум 2 варианта ответа.')
            correct_count = sum(1 for i, _ in non_empty if i in correct_indexes)
            if correct_count == 0:
                errors.append('Отметьте хотя бы один правильный ответ.')
            if question_type == 'single' and correct_count > 1:
                errors.append('Для типа «Один ответ» правильный вариант должен быть только один.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'hr/question_form.html', {
                'action': 'edit',
                'question': question,
                'categories': Category.objects.all().order_by('name'),
                'form_data': request.POST,
            })
        # Обновляем
        question.category_id = category_id
        question.text = text
        question.question_type = question_type
        question.save()
        # Удаляем старые ответы и создаём новые
        question.answers.all().delete()
        if question_type in ('single', 'multiple'):
            for i, ans_text in enumerate(answer_texts):
                ans_text = ans_text.strip()
                if ans_text:
                    Answer.objects.create(
                        question=question,
                        text=ans_text,
                        is_correct=(i in correct_indexes),
                    )
        messages.success(request, 'Вопрос обновлён.')
        return redirect('hr_questions')
    # GET
    return render(request, 'hr/question_form.html', {
        'action': 'edit',
        'question': question,
        'categories': Category.objects.all().order_by('name'),
    })

@login_required
def hr_question_delete(request, question_id):
    """Удаление вопроса."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    question = get_object_or_404(Question, id=question_id)
    if request.method == 'POST':
        # Проверяем, привязан ли вопрос к тестам
        linked_tests = question.tests.all()
        question.delete()
        if linked_tests:
            messages.warning(
                request,
                f'Вопрос удалён. Он был привязан к {linked_tests.count()} тест(ам).'
            )
        else:
            messages.success(request, 'Вопрос удалён.')
        return redirect('hr_questions')
    return render(request, 'hr/question_delete.html', {'question': question})

@login_required
def hr_tests(request):
    """Список тестов с фильтром по категории."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    category_id = request.GET.get('category')
    tests = Test.objects.select_related('category').prefetch_related('questions')
    if category_id:
        tests = tests.filter(category_id=category_id)
    tests = tests.order_by('-created_at')
    context = {
        'tests': tests,
        'categories': Category.objects.all().order_by('name'),
        'selected_category': category_id,
    }
    return render(request, 'hr/tests.html', context)

@login_required
def hr_test_add(request):
    """Добавление теста."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        pass_score = request.POST.get('pass_score', '70')
        time_limit = request.POST.get('time_limit', '20')
        question_ids = request.POST.getlist('questions')
        errors = []
        if not title:
            errors.append('Введите название теста.')
        if not category_id:
            errors.append('Выберите категорию.')
        if not question_ids:
            errors.append('Выберите хотя бы один вопрос.')

        try:
            pass_score = int(pass_score)
            if pass_score < 0 or pass_score > 100:
                errors.append('Проходной балл должен быть от 0 до 100.')
        except ValueError:
            errors.append('Проходной балл должен быть числом.')

        try:
            time_limit = int(time_limit)
            if time_limit < 1:
                errors.append('Время должно быть не менее 1 минуты.')
        except ValueError:
            errors.append('Время должно быть числом.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('hr_test_add')

        test = Test.objects.create(
            title=title,
            description=description,
            category_id=category_id,
            pass_score=pass_score,
            time_limit=time_limit,
            created_by=request.user,
        )
        test.questions.set(question_ids)
        messages.success(request, f'Тест «{title}» добавлен.')
        return redirect('hr_tests')
    context = {
        'categories': Category.objects.all().order_by('name'),
        'questions': Question.objects.select_related('category').order_by('category__name', 'text'),
    }
    return render(request, 'hr/test_form.html', context)

@login_required
def hr_test_edit(request, test_id):
    """Редактирование теста."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    test = get_object_or_404(Test, id=test_id)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        pass_score = request.POST.get('pass_score', '70')
        time_limit = request.POST.get('time_limit', '20')
        question_ids = request.POST.getlist('questions')
        errors = []
        if not title:
            errors.append('Введите название теста.')
        if not category_id:
            errors.append('Выберите категорию.')
        if not question_ids:
            errors.append('Выберите хотя бы один вопрос.')
        try:
            pass_score = int(pass_score)
            if pass_score < 0 or pass_score > 100:
                errors.append('Проходной балл должен быть от 0 до 100.')
        except ValueError:
            errors.append('Проходной балл должен быть числом.')
        try:
            time_limit = int(time_limit)
            if time_limit < 1:
                errors.append('Время должно быть не менее 1 минуты.')
        except ValueError:
            errors.append('Время должно быть числом.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('hr_test_edit', test_id=test.id)
        test.title = title
        test.description = description
        test.category_id = category_id
        test.pass_score = pass_score
        test.time_limit = time_limit
        test.save()
        test.questions.set(question_ids)
        messages.success(request, 'Тест обновлён.')
        return redirect('hr_tests')
    context = {
        'test': test,
        'categories': Category.objects.all().order_by('name'),
        'questions': Question.objects.select_related('category').order_by('category__name', 'text'),
        'selected_questions': list(test.questions.values_list('id', flat=True)),
    }
    return render(request, 'hr/test_form.html', context)

@login_required
def hr_test_delete(request, test_id):
    """Удаление теста с предупреждением."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    test = get_object_or_404(Test, id=test_id)
    if request.method == 'POST':
        assignments_count = test.assignments.count()
        title = test.title
        test.delete()
        if assignments_count:
            messages.warning(
                request,
                f'Тест «{title}» удалён вместе с {assignments_count} назначением(ями) и всеми попытками.'
            )
        else:
            messages.success(request, f'Тест «{title}» удалён.')
        return redirect('hr_tests')
    return render(request, 'hr/test_delete.html', {
        'test': test,
        'assignments_count': test.assignments.count(),
    })

@login_required
def hr_assignments(request):
    """Список назначений с фильтрами."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    status_filter = request.GET.get('status')
    test_filter = request.GET.get('test')
    assignments = Assignment.objects.select_related(
        'employee', 'test', 'assigned_by'
    ).order_by('-assigned_at')
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    if test_filter:
        assignments = assignments.filter(test_id=test_filter)
    context = {
        'assignments': assignments,
        'tests': Test.objects.all().order_by('title'),
        'selected_status': status_filter,
        'selected_test': test_filter,
        'status_choices': Assignment.STATUS_CHOICES,
    }
    return render(request, 'hr/assignments.html', context)

@login_required
def hr_assignment_add(request):
    """Назначение теста сотруднику."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    if request.method == 'POST':
        test_id = request.POST.get('test')
        employee_id = request.POST.get('employee')
        deadline_str = request.POST.get('deadline', '').strip()
        errors = []
        if not test_id:
            errors.append('Выберите тест.')
        if not employee_id:
            errors.append('Выберите сотрудника.')
        # Проверка дубля
        if test_id and employee_id:
            if Assignment.objects.filter(test_id=test_id, employee_id=employee_id).exists():
                errors.append('Этот тест уже назначен этому сотруднику.')
        deadline = None
        if deadline_str:
            try:
                from datetime import datetime
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                errors.append('Неверный формат даты.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('hr_assignment_add')
        Assignment.objects.create(
            test_id=test_id,
            employee_id=employee_id,
            assigned_by=request.user,
            deadline=deadline,
            status='assigned',
        )
        messages.success(request, 'Тест назначен сотруднику.')
        return redirect('hr_assignments')
    # Только сотрудники
    employees = User.objects.filter(profile__role='employee').order_by('last_name', 'first_name')
    context = {
        'tests': Test.objects.all().order_by('title'),
        'employees': employees,
    }
    return render(request, 'hr/assignment_form.html', context)

@login_required
def hr_assignment_delete(request, assignment_id):
    """Удаление назначения."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        employee_name = assignment.employee.get_full_name() or assignment.employee.username
        test_title = assignment.test.title
        assignment.delete()
        messages.success(
            request,
            f'Назначение «{test_title}» для {employee_name} удалено.'
        )
        return redirect('hr_assignments')
    return render(request, 'hr/assignment_delete.html', {'assignment': assignment})

@login_required
def manager_dashboard(request):
    """Дашборд руководителя — общая статистика."""
    if request.user.profile.role != 'manager':
        messages.error(request, 'Доступ только для руководителя.')
        return redirect('profile')
    # Статистика по статусам назначений
    status_stats = {
        'assigned': Assignment.objects.filter(status='assigned').count(),
        'in_progress': Assignment.objects.filter(status='in_progress').count(),
        'passed': Assignment.objects.filter(status='passed').count(),
        'failed': Assignment.objects.filter(status='failed').count(),
        'expired': Assignment.objects.filter(status='expired').count(),
    }
    # Общие счётчики
    employees_count = User.objects.filter(profile__role='employee').count()
    tests_count = Test.objects.count()
    assignments_count = Assignment.objects.count()
    attempts_count = Attempt.objects.filter(finished_at__isnull=False).count()
    # Средний процент по завершённым попыткам
    avg_percent = Attempt.objects.filter(
        finished_at__isnull=False
    ).aggregate(avg=Avg('percent'))['avg']
    avg_percent = round(avg_percent, 1) if avg_percent else 0
    # Последние 10 попыток
    recent_attempts = Attempt.objects.select_related(
        'employee', 'assignment__test'
    ).filter(finished_at__isnull=False).order_by('-finished_at')[:10]
    context = {
        'status_stats': status_stats,
        'employees_count': employees_count,
        'tests_count': tests_count,
        'assignments_count': assignments_count,
        'attempts_count': attempts_count,
        'avg_percent': avg_percent,
        'recent_attempts': recent_attempts,
    }
    return render(request, 'manager/dashboard.html', context)

@login_required
def manager_report_tests(request):
    """Отчёт по тестам."""
    if request.user.profile.role != 'manager':
        messages.error(request, 'Доступ только для руководителя.')
        return redirect('profile')
    tests = Test.objects.select_related('category').annotate(
        assignments_total=Count('assignments', distinct=True),
        passed_count=Count('assignments', filter=Q(assignments__status='passed'), distinct=True),
        failed_count=Count('assignments', filter=Q(assignments__status='failed'), distinct=True),
    ).order_by('title')
    # Средний процент по каждому тесту
    test_stats = []
    for t in tests:
        avg = Attempt.objects.filter(
            assignment__test=t,
            finished_at__isnull=False
        ).aggregate(avg=Avg('percent'))['avg']
        avg = round(avg, 1) if avg else 0
        passed = t.passed_count
        failed = t.failed_count
        total_finished = passed + failed
        pass_rate = round(passed / total_finished * 100, 1) if total_finished else 0
        test_stats.append({
            'test': t,
            'assignments_total': t.assignments_total,
            'passed': passed,
            'failed': failed,
            'avg_percent': avg,
            'pass_rate': pass_rate,
        })
    return render(request, 'manager/report_tests.html', {'test_stats': test_stats})

@login_required
def manager_report_employees(request):
    """Отчёт по сотрудникам."""
    if request.user.profile.role != 'manager':
        messages.error(request, 'Доступ только для руководителя.')
        return redirect('profile')
    employees = User.objects.filter(profile__role='employee').select_related('profile')
    employee_stats = []
    for emp in employees:
        assignments = Assignment.objects.filter(employee=emp)
        total = assignments.count()
        passed = assignments.filter(status='passed').count()
        failed = assignments.filter(status='failed').count()
        avg = Attempt.objects.filter(
            employee=emp,
            finished_at__isnull=False
        ).aggregate(avg=Avg('percent'))['avg']
        avg = round(avg, 1) if avg else 0
        last_attempt = Attempt.objects.filter(
            employee=emp,
            finished_at__isnull=False
        ).order_by('-finished_at').first()
        employee_stats.append({
            'employee': emp,
            'total': total,
            'passed': passed,
            'failed': failed,
            'avg_percent': avg,
            'last_attempt': last_attempt,
        })
    # Сортировка: сначала те, у кого больше провалов
    employee_stats.sort(key=lambda x: (-x['failed'], x['employee'].last_name))
    return render(request, 'manager/report_employees.html', {'employee_stats': employee_stats})

@login_required
def chat_messages(request):
    """API: получение последних сообщений чата."""
    messages_qs = Message.objects.select_related('sender').order_by('-created_at')[:50]
    messages_list = list(reversed(messages_qs))
    current_username = request.user.username
    data = []
    for m in messages_list:
        data.append({
            'id': m.id,
            'sender': m.sender.get_full_name() or m.sender.username,
            'text': m.text,
            'created_at': m.created_at.strftime('%H:%M'),
            'is_mine': m.sender_id == request.user.id,
        })
    return JsonResponse({'messages': data})

@login_required
def chat_send(request):
    """API: отправка сообщения."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Пустое сообщение'}, status=400)
    if len(text) > 1000:
        return JsonResponse({'error': 'Слишком длинное сообщение'}, status=400)
    Message.objects.create(sender=request.user, text=text)
    return JsonResponse({'ok': True})

@login_required
def feedback_view(request):
    """Форма обратной связи."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        text = request.POST.get('text', '').strip()
        errors = []
        if not name:
            errors.append('Введите имя.')
        if not email:
            errors.append('Введите email.')
        elif '@' not in email:
            errors.append('Введите корректный email.')
        if not text:
            errors.append('Введите сообщение.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('feedback')
        fb = Feedback.objects.create(
            name=name,
            email=email,
            text=text,
            is_sent=False,
        )
        # Отправка email через SMTP
        try:
            send_mail(
                subject=f'Обратная связь: {name}',
                message=f'От: {name} <{email}>\n\n{text}',
                from_email=None,  # возьмётся DEFAULT_FROM_EMAIL
                recipient_list=['voichukmargarita@gmail.com', email],
                fail_silently=False,
            )
            fb.is_sent = True
            fb.save()
            messages.success(
                request,
                'Спасибо! Сообщение отправлено. Мы свяжемся с вами.'
            )
        except Exception as e:
            messages.warning(
                request,
                f'Сообщение сохранено, но письмо не отправлено: {e}'
            )
        return redirect('home')
    return render(request, 'feedback.html')

@login_required
def hr_materials(request):
    """Список материалов для HR."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    materials = Material.objects.select_related('category', 'uploaded_by').order_by('-uploaded_at')
    return render(request, 'hr/materials.html', {'materials': materials})

@login_required
def hr_material_add(request):
    """Загрузка нового материала."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category_id = request.POST.get('category')
        file = request.FILES.get('file')
        errors = []
        if not title:
            errors.append('Введите название.')
        if not category_id:
            errors.append('Выберите категорию.')
        if not file:
            errors.append('Прикрепите файл.')
        else:
            allowed_ext = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.txt', '.png', '.jpg', '.jpeg')
            if not file.name.lower().endswith(allowed_ext):
                errors.append('Недопустимый формат файла. Разрешены: pdf, doc, docx, xls, xlsx, odt, txt, png, jpg.')
            if file.size > 10 * 1024 * 1024:
                errors.append('Файл слишком большой (максимум 10 МБ).')
        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('hr_material_add')
        Material.objects.create(
            title=title,
            category_id=category_id,
            file=file,
            uploaded_by=request.user,
        )
        messages.success(request, f'Материал «{title}» загружен.')
        return redirect('hr_materials')
    categories = Category.objects.all().order_by('name')
    return render(request, 'hr/material_form.html', {'categories': categories})

@login_required
def hr_material_delete(request, material_id):
    """Удаление материала."""
    if request.user.profile.role != 'hr':
        messages.error(request, 'Доступ только для HR.')
        return redirect('profile')
    material = get_object_or_404(Material, id=material_id)
    if request.method == 'POST':
        title = material.title
        material.delete()
        messages.success(request, f'Материал «{title}» удалён.')
        return redirect('hr_materials')
    return render(request, 'hr/material_delete.html', {'material': material})

def blog_list(request):
    """Страница блога — список постов."""
    posts = Post.objects.filter(is_published=True).select_related('author')
    return render(request, 'blog/list.html', {'posts': posts})

def blog_detail(request, post_id):
    """Страница поста."""
    post = get_object_or_404(Post, id=post_id, is_published=True)
    return render(request, 'blog/detail.html', {'post': post})

def search_view(request):
    """Поиск по сайту."""
    query = request.GET.get('q', '').strip()
    results = {
        'query': query,
        'questions': [],
        'tests': [],
        'employees': [],
        'materials': [],
        'posts': [],
    }
    if query:
        results['questions'] = Question.objects.filter(
            text__icontains=query
        ).select_related('category')[:20]
        results['tests'] = Test.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).select_related('category')[:20]
        # Сотрудников ищут только HR и Manager
        if request.user.is_authenticated and request.user.profile.role in ('hr', 'manager'):
            results['employees'] = User.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(username__icontains=query) |
                Q(email__icontains=query),
                profile__role='employee'
            ).select_related('profile')[:20]
        results['materials'] = Material.objects.filter(
            title__icontains=query
        ).select_related('category')[:20]
        results['posts'] = Post.objects.filter(
            Q(title__icontains=query) | Q(text__icontains=query),
            is_published=True
        )[:20]
    return render(request, 'search.html', results)