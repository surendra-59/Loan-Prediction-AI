from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles=[]):

    def decorator(view_func):

        def wrapper(request, *args, **kwargs):

            if request.user.is_authenticated:
                if request.user.user_type in allowed_roles:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, "You are not authorized to access this page.")
                    return redirect("login")

            return redirect("login")

        return wrapper

    return decorator
