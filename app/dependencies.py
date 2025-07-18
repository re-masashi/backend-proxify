# app/dependencies.py

import requests
from fastapi import Depends, HTTPException, status, Request
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from sqlalchemy.orm import Session
from typing import Dict

from .core import settings
from .database import get_db
from . import crud, models

# A simple in-memory cache to store Clerk's public keys
jwks_cache: Dict = {}

def get_jwks() -> Dict:
    """
    Retrieves and caches the JSON Web Key Set (JWKS) from Clerk.
    """
    if "keys" in jwks_cache:
        return jwks_cache

    jwks_url = f"{settings.CLERK_ISSUER_URL}/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()
        jwks_cache["keys"] = jwks["keys"]
        return jwks_cache
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch JWKS: {e}")


async def get_current_user_id(request: Request) -> str:
    """
    Verifies the Clerk JWT from the Authorization header and returns the user ID.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        token_type, token = auth_header.split()
        if token_type.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        jwks = get_jwks()
        
        # Get the unverified header to find the Key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"], "kid": key["kid"], "use": key["use"],
                    "n": key["n"], "e": key["e"]
                }
        
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Unable to find appropriate key")

        # Verify the token's signature and claims
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER_URL,
        )

        # Clerk stores the user ID in the 'sub' (subject) claim
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")

        return user_id

    except (JWTError, ExpiredSignatureError, JWTClaimsError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


async def get_current_admin_user(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Depends on the standard user auth, then checks if the user is an admin.
    """
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in our database.")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: Requires admin privileges.")
    return user
