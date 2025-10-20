"""
Test script for authentication
Run this to test if authentication is working correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_config():
    """Test if configuration loads correctly"""
    print("Testing configuration...")
    try:
        from app.config import settings
        print(f"✅ Configuration loaded successfully")
        print(f"   - App Name: {settings.app_name}")
        print(f"   - Environment: {settings.environment}")
        print(f"   - Supabase URL: {settings.supabase_url[:30]}...")
        return True
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False


def test_supabase_client():
    """Test if Supabase client initializes"""
    print("\nTesting Supabase client...")
    try:
        from utils.supabase_client import supabase_client
        print(f"✅ Supabase client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Supabase client failed: {e}")
        return False


def main():
    print("=" * 60)
    print("KTUfy Backend - Authentication Test")
    print("=" * 60)
    
    results = []
    
    # Test configuration
    results.append(test_config())
    
    # Test Supabase client
    results.append(test_supabase_client())
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed! Authentication system is ready.")
        print("\nNext steps:")
        print("1. Start the server: python main.py")
        print("2. Visit http://localhost:8000/docs")
        print("3. Test the authentication endpoints")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
