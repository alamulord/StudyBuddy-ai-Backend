from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from supabase import create_client, Client, ClientOptions
from app.core.config import settings

security = HTTPBearer()

# Global httpx client for better connection pooling and DNS caching
_shared_timeout = httpx.Timeout(300.0)
_shared_httpx_client = httpx.Client(timeout=_shared_timeout)

def get_supabase() -> Client:
    options = ClientOptions(
        httpx_client=_shared_httpx_client,
        postgrest_client_timeout=300,
        storage_client_timeout=300,
        schema="public"
    )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, options=options)

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    token = credentials.credentials.strip()
    
    # Use a client with the ANON_KEY and proper timeout for user validation
    options = ClientOptions(
        httpx_client=_shared_httpx_client,
        postgrest_client_timeout=300,
        storage_client_timeout=300
    )
    temp_supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY, options=options)
    
    last_error = None
    retries = 3
    
    for attempt in range(retries):
        try:
            if attempt > 0:
                import time
                time.sleep(1) # Simple exponential backoff or just static delay
                
            print(f"DEBUG: Validating token. Length: {len(token)} (Attempt {attempt+1}/{retries})")
            user_response = temp_supabase.auth.get_user(token)
            
            if not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials (No user found)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user_response.user
            
        except HTTPException:
            raise # Re-raise 401 immediately if it was intentional
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            print(f"DEBUG: Auth attempt {attempt+1} failed: {type(e).__name__}: {str(e)}")
            
            # Broaden retry categories for flaky network connections
            is_network_error = any(term in error_msg for term in [
                "getaddrinfo", 
                "connection", 
                "timeout", 
                "connecterror", 
                "requesttimeout",
                "handshake",
                "network"
            ])
            
            if is_network_error:
                continue # Retry on network/DNS failure
            break # Break on other errors like 403, 404, etc.
            
    # If we reached here, all retries failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication error: {str(last_error)}",
        headers={"WWW-Authenticate": "Bearer"},
    )
