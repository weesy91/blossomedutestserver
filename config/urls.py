from django.contrib import admin
from django.urls import path, include
from django.conf import settings  
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views # 👈 [핵심] 이 줄이 꼭 있어야 합니다!

# ==========================================
# [관리자 메뉴 필터링] 
# ==========================================
if not hasattr(admin.site, 'original_get_app_list'):
    admin.site.original_get_app_list = admin.site.get_app_list

def custom_get_app_list(request, app_label=None):
    app_list = admin.site.original_get_app_list(request, app_label)
    HIDDEN_MODELS = ['School', 'Publisher'] 
    
    if app_list:
        for app in app_list:
            app['models'] = [
                m for m in app['models'] 
                if m['object_name'] not in HIDDEN_MODELS
            ]
    return [app for app in app_list if app['models']]

admin.site.get_app_list = custom_get_app_list
# ==========================================

urlpatterns = [
    path('admin/', admin.site.urls),

    # 1. 접속하자마자 로그인 화면 보여주기
    path('', auth_views.LoginView.as_view(template_name='core/login.html'), name='root_login'),

    # 2. 나머지 앱들 연결
    path('core/', include(('core.urls', 'core'), namespace='core')),
    path('vocab/', include('vocab.urls')),
    path('academy/', include('academy.urls')),
    path('reports/', include('reports.urls')),
    path('exam/', include('exam.urls')),
    path('mock/', include('mock.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)