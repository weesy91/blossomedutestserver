"""
Django settings for config project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key')

# SECURITY WARNING: don't run with debug turned on in production!
# 기본값을 False로 두어 배포 환경에서 안전하게 합니다.
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'vocab',
    'academy',
    'reports',
    'exam',
    'mock',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = []


# Internationalization
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = False


# [Static Files 설정]
# HTML에서 {% static %} 태그를 쓸 때 붙는 주소
STATIC_URL = '/static/'

# collectstatic 명령어를 쳤을 때 파일이 모이는 "최종 목적지"
# Nginx는 이 폴더를 바라봅니다.
STATIC_ROOT = BASE_DIR / 'static'

# ⚠️ STATICFILES_DIRS는 잠시 주석 처리합니다.
# 이유: STATIC_ROOT와 경로가 같으면 "자기가 자기를 덮어쓰는" 에러가 납니다.
# 만약 별도의 assets 폴더가 있다면 아래 주석을 풀고 경로를 수정하세요.
# STATICFILES_DIRS = [
#     BASE_DIR / 'assets',
# ]


# [Media Files 설정]
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# [로그인/로그아웃 설정]
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:login_dispatch'
LOGOUT_REDIRECT_URL = 'core:login'

# 데이터 전송 제한 해제
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000

# 기본 키 필드 타입
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CSRF_TRUSTED_ORIGINS = [
    'http://3.38.153.166',
    'https://3.38.153.166',
    # 만약 도메인을 연결했다면 아래처럼 도메인도 추가해야 합니다.
    # 'https://blossomedu.com', 
    # 'https://www.blossomedu.com',
]