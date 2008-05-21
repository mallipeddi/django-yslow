from django.conf import settings

def should_optimize():
    """Is optimization turned ON or OFF?
    
    If settings has a YSLOW_OPTIMIZE flag, use that.
    Else use the global Django project DEBUG flag.
    """
    if hasattr(settings, 'YSLOW_OPTIMIZE'):
        return settings.YSLOW_OPTIMIZE
    else:
        return settings.DEBUG
