from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.usuarios.infrastructure.persistence.usuario_repository_impl import SqlAlchemyUsuarioRepository
from app.modules.usuarios.domain.entities import Usuario
import uuid

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    repo = SqlAlchemyUsuarioRepository(db)
    user = await repo.obtener_por_id(user_id)
    
    if user is None:
        raise credentials_exception
        
    if not user.activo:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user
