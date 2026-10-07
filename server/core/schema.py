from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class BackofficeJWTScheme(SimpleJWTScheme):
    target_class = 'core.access.BackofficeJWTAuthentication'
    name = 'jwtAuth'
