# mock/forms.py
from django import forms
from .models import MockExam

class MockExamForm(forms.ModelForm):
    class Meta:
        model = MockExam
        fields = ['title', 'exam_date', 'score', 'grade', 'wrong_listening', 'wrong_vocab', 'wrong_grammar', 'wrong_reading', 'note']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 3월 2주차 모의고사'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '원점수'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '등급'}),
            'wrong_listening': forms.NumberInput(attrs={'class': 'form-control'}),
            'wrong_vocab': forms.NumberInput(attrs={'class': 'form-control'}),
            'wrong_grammar': forms.NumberInput(attrs={'class': 'form-control'}),
            'wrong_reading': forms.NumberInput(attrs={'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '특이사항이나 코멘트'}),
        }