from django.conf import settings
from yslow import utils

def version(request):
    """Insert version info into the context.
    
    If optimization is OFF, return empty version string.
    If optimization is ON, return version string from settings.
    """
    if not utils.should_optimize():
        return {'VERSION_STRING':''}
    else:
        if hasattr(settings, 'VERSION'):
            return {'VERSION_STRING': '.' + settings.VERSION}
        else:
            return {'VERSION_STRING':'.v1'}