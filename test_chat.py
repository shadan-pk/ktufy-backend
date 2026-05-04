"""
Test script for Chat endpoints
Run this after starting the server to test the chatbot functionality

Prerequisites:
1. Start the backend server: python start.ps1
2. Have a valid user token from Supabase authentication
3. Set GEMINI_API_KEY in .env file

Usage:
    python test_chat.py
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
# Replace with your actual token from Supabase authentication
TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6InBHMjUxNmZldjhtSThRTkciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2JvanJ4cnp3Y3V6ZHVpbGZ3eXFwLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI4YWVkN2JlMS01MDFkLTQ0ZjAtYjk1MC02YWZlMTVmYjI3ZTkiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzYxMTMyMTk5LCJpYXQiOjE3NjExMjg1OTksImVtYWlsIjoic3NoYWRhbnBrQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnsiYnJhbmNoIjoiQ1MiLCJjb2xsZWdlIjoiTUVBIiwiZW1haWwiOiJzc2hhZGFucGtAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJTaGFkYW4gUGsiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInJlZ2lzdHJhdGlvbl9udW1iZXIiOiJNRUEyMkNTMDg0Iiwicm9sbF9udW1iZXIiOiIwODQiLCJzdWIiOiI4YWVkN2JlMS01MDFkLTQ0ZjAtYjk1MC02YWZlMTVmYjI3ZTkiLCJ5ZWFyX2VuZGluZyI6MjAyNiwieWVhcl9qb2luZWQiOjIwMjJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzYxMTI4NTk5fV0sInNlc3Npb25faWQiOiJiZWJiNmI2NS02NTNhLTRkNjAtODkwOS0yOGE0MzEwMzE4N2EiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.P2KD-EXxxWrYJ8iPIjCLAK40bzan20ikf7IudzexZ64"

# Headers with authentication
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


def test_chat_info():
    """Test GET /api/v1/chat/info"""
    print("\n" + "="*60)
    print("Testing GET /api/v1/chat/info")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/api/v1/chat/info", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def test_create_session():
    """Test POST /api/v1/chat/sessions"""
    print("\n" + "="*60)
    print("Testing POST /api/v1/chat/sessions")
    print("="*60)
    
    session_data = {
        "title": "Test Study Session",
        "model_name": "llama3"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/sessions",
        headers=headers,
        json=session_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def test_get_sessions():
    """Test GET /api/v1/chat/sessions"""
    print("\n" + "="*60)
    print("Testing GET /api/v1/chat/sessions")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/api/v1/chat/sessions", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def test_send_message(session_id=None):
    """Test POST /api/v1/chat/message"""
    print("\n" + "="*60)
    print("Testing POST /api/v1/chat/message")
    print("="*60)
    
    message_data = {
        "message": "Explain what is recursion in programming?",
        "session_id": session_id
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers=headers,
        json=message_data
    )
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Session ID: {data['session_id']}")
        print(f"\nUser Message: {data['message']['content']}")
        print(f"\nAI Response: {data['assistant_message']['content']}")
        return data
    else:
        print(f"Error: {response.json()}")
        return None


def test_get_session_with_messages(session_id):
    """Test GET /api/v1/chat/sessions/{session_id}"""
    print("\n" + "="*60)
    print(f"Testing GET /api/v1/chat/sessions/{session_id}")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/v1/chat/sessions/{session_id}",
        headers=headers
    )
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Session Title: {data['title']}")
        print(f"Message Count: {len(data['messages'])}")
        print("\nConversation:")
        for msg in data['messages']:
            role = "You" if msg['role'] == 'user' else "AI"
            print(f"\n{role}: {msg['content']}")
        return data
    else:
        print(f"Error: {response.json()}")
        return None


def test_update_session(session_id):
    """Test PUT /api/v1/chat/sessions/{session_id}"""
    print("\n" + "="*60)
    print(f"Testing PUT /api/v1/chat/sessions/{session_id}")
    print("="*60)
    
    update_data = {
        "title": "Updated: Recursion Study Session",
        "model_name": "llama3"
    }
    
    response = requests.put(
        f"{BASE_URL}/api/v1/chat/sessions/{session_id}",
        headers=headers,
        json=update_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def test_delete_session(session_id):
    """Test DELETE /api/v1/chat/sessions/{session_id}"""
    print("\n" + "="*60)
    print(f"Testing DELETE /api/v1/chat/sessions/{session_id}")
    print("="*60)
    
    # WARNING: This will delete the session!
    # Uncomment to test
    """
    response = requests.delete(
        f"{BASE_URL}/api/v1/chat/sessions/{session_id}",
        headers=headers
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    """
    print("⚠️  Delete test skipped (uncomment in code to test)")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("CHAT ENDPOINTS TEST SUITE")
    print("="*60)
    
    if TOKEN == "your-supabase-jwt-token-here":
        print("\n❌ ERROR: Please update the TOKEN variable with your actual Supabase token!")
        print("\nHow to get a token:")
        print("1. Log in through your frontend")
        print("2. The token is stored in SecureStore")
        print("3. Or get it from Supabase Dashboard → Authentication → Users")
        return
    
    try:
        # Test 1: Get chat info
        test_chat_info()
        
        # Test 2: Create a session
        session = test_create_session()
        session_id = session.get('id')
        
        if not session_id:
            print("\n❌ Failed to create session")
            return
        
        # Test 3: Get all sessions
        test_get_sessions()
        
        # Test 4: Send a message (creates conversation)
        chat_response = test_send_message(session_id)
        
        if not chat_response:
            print("\n❌ Failed to send message")
            return
        
        # Test 5: Send another message in same session
        print("\n" + "="*60)
        print("Testing follow-up message")
        print("="*60)
        message_data = {
            "message": "Can you give me a simple example in Python?",
            "session_id": session_id
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/chat/message",
            headers=headers,
            json=message_data
        )
        if response.status_code == 200:
            data = response.json()
            print(f"AI Response: {data['assistant_message']['content']}")
        
        # Test 6: Get session with messages
        test_get_session_with_messages(session_id)
        
        # Test 7: Update session
        test_update_session(session_id)
        
        # Test 8: Delete session (optional)
        test_delete_session(session_id)
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60)
        print(f"\nSession ID for further testing: {session_id}")
        print("\n💡 Tips:")
        print("- You can send more messages to the session")
        print("- Check the interactive docs at http://localhost:8000/docs")
        print("- Conversation context is maintained within each session")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server!")
        print("Make sure the backend server is running on http://localhost:8000")
        print("Run: python start.ps1")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
