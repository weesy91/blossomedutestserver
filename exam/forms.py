from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from core.models import StudentProfile
from academy.models import Textbook
from .models import TestPaper

User = get_user_model()

class TestPaperGenerationForm(forms.ModelForm):
    # ================= [공통 설정] =================
    teacher = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="담당 선생님",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'teacher-select'})
    )
    # [수정] queryset을 StudentProfile로 명확하게 지정
    student = forms.ModelChoiceField(
        queryset=StudentProfile.objects.none(),
        label="응시 학생",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'student-select'})
    )
    custom_title = forms.CharField(
        label="시험지 제목 (선택)", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '비워두면 자동 생성'})
    )

    # ================= [Part 1. 구문/어법 설정] =================
    syntax_textbook = forms.ModelChoiceField(
        queryset=Textbook.objects.filter(category__in=['SYNTAX', 'GRAMMAR']),
        label="구문 교재",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    syntax_start = forms.IntegerField(
        label="시작 강", required=False, initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    syntax_end = forms.IntegerField(
        label="끝 강", required=False, initial=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    syntax_count = forms.IntegerField(
        label="문항 수", required=False, initial=15,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    concept_ratio = forms.IntegerField(
        label="개념 문제 비율 (%)",
        initial=50,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-range', 'type': 'range', 
            'min': '0', 'max': '100', 'step': '10',
            'oninput': "document.getElementById('ratioVal').innerText = this.value + '%'"
        })
    )

    # ================= [Part 2. 독해 설정] =================
    reading_textbook = forms.ModelChoiceField(
        queryset=Textbook.objects.filter(category='READING'),
        label="독해 교재",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reading_start = forms.IntegerField(
        label="시작 강", required=False, initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reading_end = forms.IntegerField(
        label="끝 강", required=False, initial=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reading_count = forms.IntegerField(
        label="문항 수", required=False, initial=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = TestPaper
        fields = ['student'] 

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            if user.is_superuser:
                self.fields['teacher'].queryset = User.objects.filter(is_staff=True).order_by('username')
            elif hasattr(user, 'staff_profile'):
                # 부원장이나 일반 강사 로직
                if user.staff_profile.position == 'VICE':
                    managed = list(user.staff_profile.managed_teachers.all())
                    team = [user.id] + [t.id for t in managed]
                    self.fields['teacher'].queryset = User.objects.filter(id__in=team).order_by('username')
                else:
                    self.fields['teacher'].queryset = User.objects.filter(id=user.id)
            else:
                self.fields['teacher'].queryset = User.objects.filter(id=user.id)
            
            self.fields['teacher'].initial = user

        # 선택된 선생님에 따른 학생 목록 필터링
        if self.data.get('teacher'):
            try:
                teacher_id = int(self.data.get('teacher'))
                self.fields['student'].queryset = StudentProfile.objects.filter(
                    Q(syntax_teacher_id=teacher_id) | 
                    Q(reading_teacher_id=teacher_id) | 
                    Q(extra_class_teacher_id=teacher_id)
                ).distinct()
            except (ValueError, TypeError):
                self.fields['student'].queryset = StudentProfile.objects.none()
        elif user and not user.is_superuser:
             self.fields['student'].queryset = StudentProfile.objects.filter(
                Q(syntax_teacher=user) | Q(reading_teacher=user) | Q(extra_class_teacher=user)
             ).distinct()