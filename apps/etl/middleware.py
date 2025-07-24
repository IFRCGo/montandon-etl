from django.core.exceptions import PermissionDenied
from django.conf import settings

class MaxRequestBodySizeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.max_size = settings.MAX_REQUEST_BODY_SIZE

    def __call__(self, request):
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_length = request.META.get('CONTENT_LENGTH')
            if content_length and int(content_length) > self.max_size:
                raise PermissionDenied(f"Request payload too large (max {self.max_size} bytes).")
        return self.get_response(request)
