"""
Test script for new user management endpoints
Run this after starting the server with: python start.ps1

Make sure to:
1. Start the backend server
2. Have a valid user token from Supabase
3. Update the TOKEN variable below with your actual token
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
# Replace with your actual token from Supabase authentication
TOKEN = "your-supabase-jwt-token-here"

# Headers with authentication
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


def test_get_current_user():
    """Test GET /api/v1/auth/me"""
    print("\n" + "="*50)
    print("Testing GET /api/v1/auth/me")
    print("="*50)
    
    response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def test_update_user_profile():
    """Test PUT /api/v1/auth/me"""
    print("\n" + "="*50)
    print("Testing PUT /api/v1/auth/me")
    print("="*50)
    
    update_data = {
        "metadata": {
            "full_name": "Updated Test User",
            "semester": 5,
            "branch": "Computer Science",
            "phone": "+91-1234567890"
        }
    }
    
    response = requests.put(
        f"{BASE_URL}/api/v1/auth/me",
        headers=headers,
        json=update_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_update_email():
    """Test PUT /api/v1/auth/me - Update email"""
    print("\n" + "="*50)
    print("Testing PUT /api/v1/auth/me - Update Email")
    print("="*50)
    
    # WARNING: This will change your email!
    # Uncomment only if you want to test email update
    """
    update_data = {
        "email": "newemail@example.com"
    }
    
    response = requests.put(
        f"{BASE_URL}/api/v1/auth/me",
        headers=headers,
        json=update_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    """
    print("Email update test skipped (uncomment to test)")


def test_change_password():
    """Test POST /api/v1/auth/change-password"""
    print("\n" + "="*50)
    print("Testing POST /api/v1/auth/change-password")
    print("="*50)
    
    # WARNING: This will change your password!
    # Uncomment only if you want to test password change
    """
    password_data = {
        "new_password": "NewSecurePassword123!"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/change-password",
        headers=headers,
        json=password_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    """
    print("Password change test skipped (uncomment to test)")


def test_verify_email():
    """Test POST /api/v1/auth/verify-email"""
    print("\n" + "="*50)
    print("Testing POST /api/v1/auth/verify-email")
    print("="*50)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/verify-email",
        headers=headers
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_delete_user_unauthorized():
    """Test DELETE /api/v1/users/{user_id} - Unauthorized attempt"""
    print("\n" + "="*50)
    print("Testing DELETE /api/v1/users/{user_id} - Unauthorized")
    print("="*50)
    
    # Try to delete a different user (should fail)
    fake_user_id = "00000000-0000-0000-0000-000000000000"
    
    response = requests.delete(
        f"{BASE_URL}/api/v1/auth/users/{fake_user_id}",
        headers=headers
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_delete_own_user():
    """Test DELETE /api/v1/users/{user_id} - Delete own account"""
    print("\n" + "="*50)
    print("Testing DELETE /api/v1/users/{user_id} - Delete Own Account")
    print("="*50)
    
    # WARNING: This will delete your account!
    # Uncomment only if you want to test account deletion
    """
    # First get the current user ID
    user_data = test_get_current_user()
    user_id = user_data.get("user_id")
    
    response = requests.delete(
        f"{BASE_URL}/api/v1/auth/users/{user_id}",
        headers=headers
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    """
    print("Account deletion test skipped (uncomment to test)")


def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("USER MANAGEMENT ENDPOINTS TEST SUITE")
    print("="*50)
    
    if TOKEN == "your-supabase-jwt-token-here":
        print("\n❌ ERROR: Please update the TOKEN variable with your actual Supabase token!")
        print("You can get a token by:")
        print("1. Logging in through your frontend")
        print("2. Using Supabase Auth API")
        print("3. Checking your browser's local storage")
        return
    
    try:
        # Safe tests (read-only or metadata updates)
        test_get_current_user()
        test_update_user_profile()
        test_verify_email()
        test_delete_user_unauthorized()
        
        # Dangerous tests (commented out by default)
        test_update_email()
        test_change_password()
        test_delete_own_user()
        
        print("\n" + "="*50)
        print("✅ All safe tests completed!")
        print("="*50)
        print("\n⚠️  Note: Destructive tests (email update, password change, account deletion)")
        print("are commented out for safety. Uncomment them in the code if you want to test them.")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server!")
        print("Make sure the backend server is running on http://localhost:8000")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    main()
