import random

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import ChoiceFormSet, CourseForm, QuestionForm, QuizForm, SignUpForm
from .models import (Choice, Course, Profile, Question, Quiz, Result,
                      StudentAnswer, StudentAttempt)


# -----------------------------
# ROLE CHECK HELPERS
# -----------------------------
def is_teacher(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'teacher'


def is_student(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'student'


def is_admin_or_teacher(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role in ('admin', 'teacher')


# -----------------------------
# AUTHENTICATION
# -----------------------------
class UserLoginView(LoginView):
    template_name = 'registration/login.html'


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('login')


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully!")
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


# -----------------------------
# DASHBOARD (role-based)
# -----------------------------
@login_required
def dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        Profile.objects.create(user=request.user, role='student')
        profile = request.user.profile

    if profile.role == 'teacher':
        courses = Course.objects.filter(teacher=request.user)
        quizzes = Quiz.objects.filter(created_by=request.user)
        total_attempts = StudentAttempt.objects.filter(quiz__created_by=request.user).count()
        context = {'courses': courses, 'quizzes': quizzes, 'total_attempts': total_attempts}
        return render(request, 'quiz/teacher_dashboard.html', context)

    elif profile.role == 'student':
        courses = request.user.courses_enrolled.all()
        available_quizzes = Quiz.objects.filter(course__in=courses, is_published=True)
        my_attempts = StudentAttempt.objects.filter(student=request.user).order_by('-started_at')[:5]
        context = {'courses': courses, 'available_quizzes': available_quizzes, 'my_attempts': my_attempts}
        return render(request, 'quiz/student_dashboard.html', context)

    else:  # admin
        context = {
            'total_users': User_count(),
            'total_courses': Course.objects.count(),
            'total_quizzes': Quiz.objects.count(),
            'total_attempts': StudentAttempt.objects.count(),
        }
        return render(request, 'quiz/admin_dashboard.html', context)


def User_count():
    from django.contrib.auth.models import User
    return User.objects.count()


# -----------------------------
# COURSE CRUD (Teacher/Admin)
# -----------------------------
@login_required
@user_passes_test(is_admin_or_teacher)
def course_list(request):
    query = request.GET.get('q', '')
    courses = Course.objects.filter(teacher=request.user)
    if query:
        courses = courses.filter(Q(name__icontains=query) | Q(code__icontains=query))
    paginator = Paginator(courses.order_by('-created_at'), 6)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quiz/course_list.html', {'page_obj': page_obj, 'query': query})


@login_required
@user_passes_test(is_admin_or_teacher)
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            form.save_m2m()
            messages.success(request, "Course created successfully.")
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'quiz/course_form.html', {'form': form, 'title': 'Create Course'})


@login_required
@user_passes_test(is_admin_or_teacher)
def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated successfully.")
            return redirect('course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'quiz/course_form.html', {'form': form, 'title': 'Update Course'})


@login_required
@user_passes_test(is_admin_or_teacher)
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    if request.method == 'POST':
        course.delete()
        messages.success(request, "Course deleted successfully.")
        return redirect('course_list')
    return render(request, 'quiz/course_confirm_delete.html', {'course': course})


# -----------------------------
# QUIZ CRUD (Teacher)
# -----------------------------
@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_list(request):
    query = request.GET.get('q', '')
    quizzes = Quiz.objects.filter(created_by=request.user)
    if query:
        quizzes = quizzes.filter(title__icontains=query)
    paginator = Paginator(quizzes.order_by('-created_at'), 6)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quiz/quiz_list.html', {'page_obj': page_obj, 'query': query})


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_create(request):
    if request.method == 'POST':
        form = QuizForm(request.POST, teacher=request.user)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.created_by = request.user
            quiz.save()
            messages.success(request, "Quiz created. Now add questions!")
            return redirect('question_list', quiz_id=quiz.id)
    else:
        form = QuizForm(teacher=request.user)
    return render(request, 'quiz/quiz_form.html', {'form': form, 'title': 'Create Quiz'})


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_update(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz, teacher=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz updated successfully.")
            return redirect('quiz_list')
    else:
        form = QuizForm(instance=quiz, teacher=request.user)
    return render(request, 'quiz/quiz_form.html', {'form': form, 'title': 'Update Quiz'})


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_delete(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, created_by=request.user)
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Quiz deleted successfully.")
        return redirect('quiz_list')
    return render(request, 'quiz/quiz_confirm_delete.html', {'quiz': quiz})


# -----------------------------
# QUESTION BANK CRUD
# -----------------------------
@login_required
@user_passes_test(is_admin_or_teacher)
def question_list(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, created_by=request.user)
    questions = quiz.questions.all()
    return render(request, 'quiz/question_list.html', {'quiz': quiz, 'questions': questions})


@login_required
@user_passes_test(is_admin_or_teacher)
def question_create(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, created_by=request.user)
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()
            formset = ChoiceFormSet(request.POST, instance=question)
            if formset.is_valid():
                formset.save()
            messages.success(request, "Question added successfully.")
            return redirect('question_list', quiz_id=quiz.id)
        formset = ChoiceFormSet(request.POST)
    else:
        form = QuestionForm()
        formset = ChoiceFormSet()
    return render(request, 'quiz/question_form.html',
                  {'form': form, 'formset': formset, 'quiz': quiz, 'title': 'Add Question'})


@login_required
@user_passes_test(is_admin_or_teacher)
def question_update(request, pk):
    question = get_object_or_404(Question, pk=pk, quiz__created_by=request.user)
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        formset = ChoiceFormSet(request.POST, instance=question)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Question updated successfully.")
            return redirect('question_list', quiz_id=question.quiz.id)
    else:
        form = QuestionForm(instance=question)
        formset = ChoiceFormSet(instance=question)
    return render(request, 'quiz/question_form.html',
                  {'form': form, 'formset': formset, 'quiz': question.quiz, 'title': 'Update Question'})


@login_required
@user_passes_test(is_admin_or_teacher)
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk, quiz__created_by=request.user)
    quiz_id = question.quiz.id
    if request.method == 'POST':
        question.delete()
        messages.success(request, "Question deleted successfully.")
        return redirect('question_list', quiz_id=quiz_id)
    return render(request, 'quiz/question_confirm_delete.html', {'question': question})


# -----------------------------
# STUDENT: TAKE QUIZ
# -----------------------------
@login_required
@user_passes_test(is_student)
def available_quizzes(request):
    courses = request.user.courses_enrolled.all()
    quizzes = Quiz.objects.filter(course__in=courses, is_published=True)
    query = request.GET.get('q', '')
    if query:
        quizzes = quizzes.filter(title__icontains=query)
    paginator = Paginator(quizzes, 6)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quiz/available_quizzes.html', {'page_obj': page_obj, 'query': query})


@login_required
@user_passes_test(is_student)
def start_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    if not quiz.is_active():
        messages.error(request, "This quiz is not currently active.")
        return redirect('available_quizzes')

    existing = StudentAttempt.objects.filter(student=request.user, quiz=quiz, is_completed=False).first()
    if existing:
        attempt = existing
    else:
        attempt = StudentAttempt.objects.create(student=request.user, quiz=quiz)

    questions = list(quiz.questions.prefetch_related('choices'))
    if quiz.randomize_questions:
        random.shuffle(questions)

    return render(request, 'quiz/take_quiz.html', {
        'quiz': quiz, 'attempt': attempt, 'questions': questions,
        'time_remaining': attempt.time_remaining_seconds(),
    })


@login_required
@user_passes_test(is_student)
def submit_quiz(request, attempt_id):
    attempt = get_object_or_404(StudentAttempt, pk=attempt_id, student=request.user)
    if attempt.is_completed:
        return redirect('view_result', attempt_id=attempt.id)

    if request.method == 'POST':
        quiz = attempt.quiz
        correct_count = 0
        wrong_count = 0
        total_score = 0

        for question in quiz.questions.all():
            answer, _ = StudentAnswer.objects.get_or_create(attempt=attempt, question=question)

            if question.question_type in ('mcq_single', 'true_false'):
                selected_id = request.POST.get(f'question_{question.id}')
                answer.selected_choices.clear()
                is_correct = False
                if selected_id:
                    choice = Choice.objects.filter(pk=selected_id, question=question).first()
                    if choice:
                        answer.selected_choices.add(choice)
                        is_correct = choice.is_correct
                answer.is_correct = is_correct

            elif question.question_type == 'mcq_multi':
                selected_ids = request.POST.getlist(f'question_{question.id}')
                answer.selected_choices.clear()
                correct_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
                selected_ids_int = set(int(i) for i in selected_ids) if selected_ids else set()
                for cid in selected_ids_int:
                    choice = Choice.objects.filter(pk=cid, question=question).first()
                    if choice:
                        answer.selected_choices.add(choice)
                answer.is_correct = (selected_ids_int == correct_ids and len(correct_ids) > 0)

            else:  # short_answer
                text = request.POST.get(f'question_{question.id}', '').strip()
                answer.text_answer = text
                answer.is_correct = text.lower() == question.short_answer_text.strip().lower()

            if answer.is_correct:
                answer.marks_awarded = question.marks
                correct_count += 1
                total_score += question.marks
            else:
                wrong_count += 1
                if quiz.negative_marking:
                    penalty = float(quiz.negative_mark_value)
                    answer.marks_awarded = -penalty
                    total_score -= penalty
                else:
                    answer.marks_awarded = 0

            answer.save()

        attempt.is_completed = True
        attempt.submitted_at = timezone.now()
        attempt.score = max(0, total_score)
        attempt.save()

        total_marks = quiz.total_marks or 1
        percentage = (float(attempt.score) / total_marks) * 100 if total_marks else 0

        Result.objects.update_or_create(
            attempt=attempt,
            defaults={
                'total_marks': quiz.total_marks,
                'marks_obtained': attempt.score,
                'percentage': round(percentage, 2),
                'correct_count': correct_count,
                'wrong_count': wrong_count,
            }
        )
        messages.success(request, "Quiz submitted successfully!")
        return redirect('view_result', attempt_id=attempt.id)

    return redirect('start_quiz', quiz_id=attempt.quiz.id)


@login_required
def view_result(request, attempt_id):
    attempt = get_object_or_404(StudentAttempt, pk=attempt_id)
    if attempt.student != request.user and not is_admin_or_teacher(request.user):
        messages.error(request, "You are not authorized to view this result.")
        return redirect('dashboard')
    result = getattr(attempt, 'result', None)
    return render(request, 'quiz/result.html', {'attempt': attempt, 'result': result})


@login_required
@user_passes_test(is_student)
def result_history(request):
    attempts = StudentAttempt.objects.filter(student=request.user, is_completed=True).order_by('-submitted_at')
    paginator = Paginator(attempts, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quiz/result_history.html', {'page_obj': page_obj})


@login_required
def leaderboard(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    results = Result.objects.filter(attempt__quiz=quiz).select_related('attempt__student') \
        .order_by('-marks_obtained', 'attempt__submitted_at')
    return render(request, 'quiz/leaderboard.html', {'quiz': quiz, 'results': results})


@login_required
@user_passes_test(is_admin_or_teacher)
def performance_report(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, created_by=request.user)
    results = Result.objects.filter(attempt__quiz=quiz)
    stats = results.aggregate(
        avg_score=Avg('marks_obtained'),
        avg_percentage=Avg('percentage'),
        total_attempts=Count('id'),
    )
    return render(request, 'quiz/performance_report.html', {'quiz': quiz, 'results': results, 'stats': stats})


@login_required
@user_passes_test(is_student)
def generate_certificate(request, attempt_id):
    attempt = get_object_or_404(StudentAttempt, pk=attempt_id, student=request.user)
    result = get_object_or_404(Result, attempt=attempt)
    if result.percentage >= 50:
        result.generate_certificate_code()
        return render(request, 'quiz/certificate.html', {'result': result, 'attempt': attempt})
    messages.error(request, "Certificate available only for passing scores (50%+).")
    return redirect('view_result', attempt_id=attempt.id)
