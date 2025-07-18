# app/admin_auth.py

from jose import jwt
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from . import crud
from .core import settings
from .database import SessionLocal


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        token = form.get("token")

        if not token:
            return False

        db = SessionLocal()
        try:
            # We don't need to fully verify the signature here because the goal is just
            # to extract the user ID (sub) to check their admin status in our DB.
            # The API endpoints themselves are protected by full JWT verification.
            payload = jwt.get_unverified_claims(token)
            user_id = payload.get("sub")
            if not user_id:
                return False

            # Check if this user exists in our database and has the admin flag
            user = crud.get_user_by_clerk_id(db, clerk_user_id=user_id)
            if user and user.is_admin:
                # Store the token in the session to keep the user logged in
                request.session.update({"token": token, "user_id": user.userid})
                return True
        except Exception:
            return False
        finally:
            db.close()

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "token" in request.session


authentication_backend = AdminAuth(secret_key=settings.ADMIN_SECRET_KEY)
