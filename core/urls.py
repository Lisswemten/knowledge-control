from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    # Личный кабинет сотрудника
    path('employee/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/history/', views.employee_history, name='employee_history'),
    # Прохождение теста
    path('employee/test/<int:assignment_id>/start/', views.test_start, name='test_start'),
    path('employee/test/<int:assignment_id>/process/', views.test_process, name='test_process'),
    path('employee/test/<int:assignment_id>/submit/', views.test_submit, name='test_submit'),
    path('employee/result/<int:attempt_id>/', views.test_result, name='test_result'),
    # HR-панель
    path('hr/', views.hr_dashboard, name='hr_dashboard'),
    # HR — категории
    path('hr/categories/', views.hr_categories, name='hr_categories'),
    path('hr/categories/add/', views.hr_category_add, name='hr_category_add'),
    path('hr/categories/<int:category_id>/edit/', views.hr_category_edit, name='hr_category_edit'),
    path('hr/categories/<int:category_id>/delete/', views.hr_category_delete, name='hr_category_delete'),
    # HR — вопросы
    path('hr/questions/', views.hr_questions, name='hr_questions'),
    path('hr/questions/add/', views.hr_question_add, name='hr_question_add'),
    path('hr/questions/<int:question_id>/edit/', views.hr_question_edit, name='hr_question_edit'),
    path('hr/questions/<int:question_id>/delete/', views.hr_question_delete, name='hr_question_delete'),
    # HR — тесты
    path('hr/tests/', views.hr_tests, name='hr_tests'),
    path('hr/tests/add/', views.hr_test_add, name='hr_test_add'),
    path('hr/tests/<int:test_id>/edit/', views.hr_test_edit, name='hr_test_edit'),
    path('hr/tests/<int:test_id>/delete/', views.hr_test_delete, name='hr_test_delete'),
    # HR — назначения
    path('hr/assignments/', views.hr_assignments, name='hr_assignments'),
    path('hr/assignments/add/', views.hr_assignment_add, name='hr_assignment_add'),
    path('hr/assignments/<int:assignment_id>/delete/', views.hr_assignment_delete, name='hr_assignment_delete'),
    # Панель руководителя
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/reports/tests/', views.manager_report_tests, name='manager_report_tests'),
    path('manager/reports/employees/', views.manager_report_employees, name='manager_report_employees'),
    # Чат
    path('chat/messages/', views.chat_messages, name='chat_messages'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('feedback/', views.feedback_view, name='feedback'),
    # HR — материалы
    path('hr/materials/', views.hr_materials, name='hr_materials'),
    path('hr/materials/add/', views.hr_material_add, name='hr_material_add'),
    path('hr/materials/<int:material_id>/delete/', views.hr_material_delete, name='hr_material_delete'),
    # Блог
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<int:post_id>/', views.blog_detail, name='blog_detail'),
    # Поиск
    path('search/', views.search_view, name='search'),
]