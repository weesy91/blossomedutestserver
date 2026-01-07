# core/models/popup.py

from django.db import models
from django.utils import timezone
from .organization import Branch

class Popup(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name="소속 지점 (비워두면 전체)", related_name='popups', null=True, blank=True)
    title = models.CharField(max_length=100, verbose_name="팝업 제목")
    image = models.ImageField(upload_to='popups/', verbose_name="팝업 이미지", blank=True, null=True)
    content = models.TextField(verbose_name="팝업 텍스트 내용", blank=True)
    link = models.URLField(verbose_name="클릭 시 이동할 주소", blank=True, null=True)
    
    start_date = models.DateTimeField(verbose_name="게시 시작일", default=timezone.now)
    end_date = models.DateTimeField(verbose_name="게시 종료일")
    is_active = models.BooleanField(default=True, verbose_name="활성화 여부")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.branch.name}] {self.title}"

    class Meta:
        verbose_name = "메인 팝업 관리"
        verbose_name_plural = "메인 팝업 관리"