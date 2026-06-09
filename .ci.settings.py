COMPRESS_OUTPUT_DIR = 'cache'
STATICFILES_FINDERS += ('compressor.finders.CompressorFinder',)
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ['CI_MYSQL_DATABASE'],
        'USER': os.environ['CI_MYSQL_USER'],
        'PASSWORD': os.environ['CI_MYSQL_PASSWORD'],
        'HOST': os.environ['CI_MYSQL_HOST'],
        'PORT': int(os.environ['CI_MYSQL_PORT']),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    },
}
