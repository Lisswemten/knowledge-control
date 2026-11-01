from django.contrib import admin
from .models import Profile, Category, Question, Answer, Test, Post
from .models import Assignment, Attempt, AttemptAnswer, Message, Feedback, Material

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'position', 'phone')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

class AnswerInline(admin.TabularInline):
    """Inline для добавления ответов прямо в вопрос."""
    model = Answer
    extra = 4
    fields = ('text', 'is_correct')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'category', 'question_type', 'created_by', 'created_at')
    list_filter = ('category', 'question_type')
    search_fields = ('text',)
    inlines = [AnswerInline]
    def short_text(self, obj):
        return obj.text[:80]
    short_text.short_description = 'Текст вопроса'

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'pass_score', 'time_limit', 'created_at')
    list_filter = ('category',)
    search_fields = ('title', 'description')
    filter_horizontal = ('questions',)

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'test', 'status', 'assigned_by', 'assigned_at', 'deadline')
    list_filter = ('status', 'test__category')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'test__title')
    date_hierarchy = 'assigned_at'

class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    fields = ('question', 'text_answer', 'is_correct')
    readonly_fields = ('question',)

@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('employee', 'get_test', 'score', 'total', 'percent', 'passed', 'started_at', 'finished_at')
    list_filter = ('passed', 'assignment__test')
    search_fields = ('employee__username', 'assignment__test__title')
    inlines = [AttemptAnswerInline]
    def get_test(self, obj):
        return obj.assignment.test.title
    get_test.short_description = 'Тест'

@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct')
    list_filter = ('is_correct',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'short_text', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('sender__username', 'text')
    readonly_fields = ('sender', 'text', 'created_at')
    def short_text(self, obj):
        return obj.text[:60]
    short_text.short_description = 'Текст'

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'short_text', 'is_sent', 'created_at')
    list_filter = ('is_sent', 'created_at')
    search_fields = ('name', 'email', 'text')
    readonly_fields = ('name', 'email', 'text', 'created_at')
    def short_text(self, obj):
        return obj.text[:60]
    short_text.short_description = 'Текст'

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'uploaded_by', 'uploaded_at')
    list_filter = ('category',)
    search_fields = ('title',)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'text')