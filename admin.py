from django.contrib import admin

from .models import (Choice, Course, Profile, Question, Quiz, Result,
                      StudentAnswer, StudentAttempt)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'teacher', 'created_at')
    search_fields = ('code', 'name')
    list_filter = ('teacher',)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'question_type', 'marks')
    list_filter = ('question_type', 'quiz')
    search_fields = ('text',)
    inlines = [ChoiceInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'created_by', 'total_marks', 'is_published', 'created_at')
    list_filter = ('is_published', 'course')
    search_fields = ('title',)


@admin.register(StudentAttempt)
class StudentAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'started_at', 'is_completed', 'score')
    list_filter = ('is_completed', 'quiz')
    search_fields = ('student__username',)


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct', 'marks_awarded')


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'marks_obtained', 'total_marks', 'percentage', 'generated_at')
    search_fields = ('attempt__student__username',)
