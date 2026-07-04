from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Choice, Course, Profile, Question, Quiz


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=(('student', 'Student'), ('teacher', 'Teacher')))
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            if name == 'role':
                field.widget.attrs['class'] = (existing + ' form-select').strip()
            else:
                field.widget.attrs['class'] = (existing + ' form-control').strip()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.create(user=user, role=self.cleaned_data['role'])
        return user


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'description', 'students']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'students': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = User.objects.filter(profile__role='student')
        self.fields['students'].required = False
        for name, field in self.fields.items():
            if name != 'students':
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' form-control').strip()

    def clean_code(self):
        code = self.cleaned_data.get('code')
        qs = Course.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A course with this code already exists.")
        return code


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['course', 'title', 'description', 'duration_minutes', 'negative_marking',
                  'negative_mark_value', 'randomize_questions', 'is_published', 'start_time', 'end_time']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields['course'].queryset = Course.objects.filter(teacher=teacher)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'form-check-input'
            elif isinstance(widget, forms.Select):
                widget.attrs['class'] = 'form-select'
            else:
                existing = widget.attrs.get('class', '')
                widget.attrs['class'] = (existing + ' form-control').strip()

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned_data

    def clean_duration_minutes(self):
        duration = self.cleaned_data.get('duration_minutes')
        if duration <= 0:
            raise forms.ValidationError("Duration must be greater than zero.")
        return duration


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'marks', 'short_answer_text', 'order']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs['class'] = 'form-select'
            else:
                existing = widget.attrs.get('class', '')
                widget.attrs['class'] = (existing + ' form-control').strip()

    def clean_marks(self):
        marks = self.cleaned_data.get('marks')
        if marks <= 0:
            raise forms.ValidationError("Marks must be greater than zero.")
        return marks


ChoiceFormSet = forms.inlineformset_factory(
    Question, Choice, fields=['text', 'is_correct'], extra=4, can_delete=True,
    widgets={'text': forms.TextInput(attrs={'placeholder': 'Choice text'})}
)


class StudentAnswerForm(forms.Form):
    """Dynamically built per-question form is handled in the view;
    this is kept simple since answers are processed manually per question type."""
    pass
