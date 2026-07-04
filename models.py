import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# -----------------------------
# USER / ROLE MANAGEMENT
# -----------------------------
class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_admin_role(self):
        return self.role == 'admin'


# -----------------------------
# COURSE MANAGEMENT
# -----------------------------
class Course(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught',
                                 limit_choices_to={'profile__role': 'teacher'})
    students = models.ManyToManyField(User, related_name='courses_enrolled', blank=True,
                                       limit_choices_to={'profile__role': 'student'})
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


# -----------------------------
# QUIZ MANAGEMENT
# -----------------------------
class Quiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes_created')
    duration_minutes = models.PositiveIntegerField(default=10, help_text="Timer duration in minutes")
    total_marks = models.PositiveIntegerField(default=0, editable=False)
    negative_marking = models.BooleanField(default=False)
    negative_mark_value = models.DecimalField(max_digits=4, decimal_places=2, default=0.25)
    randomize_questions = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def update_total_marks(self):
        total = self.questions.aggregate(models.Sum('marks'))['marks__sum'] or 0
        self.total_marks = total
        self.save(update_fields=['total_marks'])

    def is_active(self):
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return self.is_published

    def question_count(self):
        return self.questions.count()


# -----------------------------
# QUESTION BANK
# -----------------------------
class Question(models.Model):
    QUESTION_TYPES = (
        ('mcq_single', 'Multiple Choice (Single Answer)'),
        ('mcq_multi', 'Multiple Choice (Multiple Answers)'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short Answer'),
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=15, choices=QUESTION_TYPES, default='mcq_single')
    marks = models.PositiveIntegerField(default=1)
    short_answer_text = models.CharField(max_length=255, blank=True,
                                          help_text="Correct answer text for short-answer questions")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:60]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.quiz.update_total_marks()


# -----------------------------
# CHOICES FOR MCQ / TRUE-FALSE
# -----------------------------
class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"


# -----------------------------
# STUDENT ATTEMPTS
# -----------------------------
class StudentAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts',
                                 limit_choices_to={'profile__role': 'student'})
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        unique_together = ('student', 'quiz', 'started_at')

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"

    def time_remaining_seconds(self):
        if self.is_completed:
            return 0
        elapsed = (timezone.now() - self.started_at).total_seconds()
        total = self.quiz.duration_minutes * 60
        remaining = total - elapsed
        return max(0, int(remaining))


class StudentAnswer(models.Model):
    attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    text_answer = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)
    marks_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return f"Answer for {self.question} by {self.attempt.student.username}"


# -----------------------------
# RESULTS
# -----------------------------
class Result(models.Model):
    attempt = models.OneToOneField(StudentAttempt, on_delete=models.CASCADE, related_name='result')
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True)
    certificate_code = models.CharField(max_length=20, blank=True, unique=True, null=True)

    def __str__(self):
        return f"Result: {self.attempt.student.username} - {self.attempt.quiz.title}"

    def generate_certificate_code(self):
        if not self.certificate_code:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            self.certificate_code = f"CERT-{code}"
            self.save(update_fields=['certificate_code'])
        return self.certificate_code
