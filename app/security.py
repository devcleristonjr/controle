from __future__ import annotations

from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*roles: str):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.perfil not in roles:
                abort(403)
            return view_function(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view_function):
    return role_required("ADMIN")(view_function)
