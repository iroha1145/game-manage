from fastapi import HTTPException, Request

from .models import Principal


def require_user(request: Request) -> Principal:
    # Never trust a user_id supplied in a header/body or preauthentication cookie.
    session = request.app.state.identity.authenticate(request.cookies.get('__Host-ga_session'))
    if session is None:
        raise HTTPException(status_code=401, detail='authentication_required')
    return session.principal
