"""
Supabase client utility
Provides initialized Supabase client for the application
"""
from supabase import create_client, Client
from app.config import settings


def get_supabase_client() -> Client:
    """
    Create and return a Supabase client instance
    Uses the anon key for client-side operations
    """
    try:
        supabase: Client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_anon_key
        )
        return supabase
    except TypeError:
        # Fallback for older supabase-py versions
        supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )
        return supabase


def get_supabase_admin_client() -> Client:
    """
    Create and return a Supabase admin client instance
    Uses the service role key for admin operations
    WARNING: Use this only for server-side operations that bypass RLS
    """
    try:
        supabase: Client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_key
        )
        return supabase
    except TypeError:
        # Fallback for older supabase-py versions
        supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
        return supabase


# Create global client instances
supabase_client = get_supabase_client()
supabase_admin_client = get_supabase_admin_client()
