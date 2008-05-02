from django.conf import settings
def version(request):
    """Insert version info into the context.
    
    If DEBUG mode is ON, return empty version string.
    If DEBUG mode is OFF, return version string from settings.
    """
    if settings.DEBUG:
        return {'VERSION_STRING':''}
    else:
        return {'VERSION_STRING': '.' + settings.VERSION}