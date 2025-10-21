# User Management Endpoints Documentation

## Overview
These endpoints allow users to manage their profiles, change passwords, verify emails, and delete accounts.

## Base URL
```
http://localhost:8000/api/v1/auth
```

---

## Endpoints

### 1. ✅ GET /api/v1/auth/me
**Get Current User Profile**

Get the authenticated user's profile information.

**Authentication Required**: Yes (Bearer token)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "student@ktu.edu.in",
  "role": "authenticated",
  "metadata": {
    "full_name": "John Doe",
    "semester": 4,
    "branch": "CSE"
  },
  "created_at": "2025-10-20T10:30:00Z"
}
```

---

### 2. ✨ PUT /api/v1/auth/me
**Update User Profile**

Update the authenticated user's email and/or metadata.

**Authentication Required**: Yes (Bearer token)

**Request Body:**
```json
{
  "email": "newemail@ktu.edu.in",  // Optional
  "metadata": {                     // Optional
    "full_name": "Updated Name",
    "semester": 5,
    "branch": "CSE",
    "phone": "+91-1234567890"
  }
}
```

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "full_name": "Updated Name",
      "semester": 5,
      "branch": "CSE"
    }
  }'
```

**Response (200 OK):**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "newemail@ktu.edu.in",
  "role": "authenticated",
  "metadata": {
    "full_name": "Updated Name",
    "semester": 5,
    "branch": "CSE",
    "phone": "+91-1234567890"
  },
  "created_at": "2025-10-20T10:30:00Z"
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "No update data provided"
}
```

---

### 3. 🔐 POST /api/v1/auth/change-password
**Change Password**

Change the authenticated user's password.

**Authentication Required**: Yes (Bearer token)

**Request Body:**
```json
{
  "new_password": "NewSecurePassword123!"
}
```

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/change-password" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_password": "NewSecurePassword123!"
  }'
```

**Response (200 OK):**
```json
{
  "message": "Password changed successfully",
  "success": true
}
```

**Validation:**
- Password must be at least 8 characters long

**Error (422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "loc": ["body", "new_password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

---

### 4. 📧 POST /api/v1/auth/verify-email
**Send Verification Email**

Send an email verification link to the authenticated user's email.

**Authentication Required**: Yes (Bearer token)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/verify-email" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK) - Email already verified:**
```json
{
  "message": "Email is already verified",
  "success": true
}
```

**Response (200 OK) - Verification email sent:**
```json
{
  "message": "Verification email sent successfully",
  "success": true
}
```

---

### 5. 🗑️ DELETE /api/v1/auth/users/{user_id}
**Delete User Account**

Delete a user account. Users can only delete their own account unless they have admin privileges.

**Authentication Required**: Yes (Bearer token)

**Path Parameters:**
- `user_id` (string): The UUID of the user to delete

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/auth/users/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
```json
{
  "message": "User account deleted successfully",
  "success": true
}
```

**Error (403 Forbidden) - Attempting to delete another user:**
```json
{
  "detail": "You can only delete your own account"
}
```

---

## Authentication

All endpoints require a valid Supabase JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Getting a Token

1. **Through Frontend Login:**
   - Log in via your React Native app
   - The token is automatically stored in secure storage
   - Use the token from `SecureStore.getItemAsync('supabase_token')`

2. **Using Supabase Auth API:**
   ```bash
   curl -X POST "https://your-project.supabase.co/auth/v1/token?grant_type=password" \
     -H "apikey: YOUR_ANON_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user@example.com",
       "password": "password123"
     }'
   ```

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Invalid authentication credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "You can only delete your own account"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error updating profile: [error message]"
}
```

---

## Testing

### Using the Test Script

1. Start the backend server:
   ```bash
   python start.ps1
   ```

2. Get your authentication token (from frontend or Supabase)

3. Update the token in `test_user_endpoints.py`:
   ```python
   TOKEN = "your-actual-token-here"
   ```

4. Run the test script:
   ```bash
   python test_user_endpoints.py
   ```

### Using Postman

1. Import the following collection or create requests manually
2. Set up environment variables:
   - `BASE_URL`: http://localhost:8000
   - `TOKEN`: Your Supabase JWT token

3. Add Authorization header to all requests:
   - Type: Bearer Token
   - Token: {{TOKEN}}

---

## Frontend Integration (React Native)

### Example: Update User Profile

```typescript
import { supabase } from './supabaseClient';
import api from './utils/api';

async function updateUserProfile(metadata: any) {
  try {
    // Get current session
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    // Call backend endpoint
    const response = await api.put('/auth/me', {
      metadata: metadata
    }, {
      headers: {
        'Authorization': `Bearer ${session.access_token}`
      }
    });

    console.log('Profile updated:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error updating profile:', error);
    throw error;
  }
}

// Usage
updateUserProfile({
  full_name: 'John Doe',
  semester: 5,
  branch: 'CSE'
});
```

### Example: Change Password

```typescript
async function changePassword(newPassword: string) {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    const response = await api.post('/auth/change-password', {
      new_password: newPassword
    }, {
      headers: {
        'Authorization': `Bearer ${session.access_token}`
      }
    });

    console.log('Password changed:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error changing password:', error);
    throw error;
  }
}
```

### Example: Send Verification Email

```typescript
async function sendVerificationEmail() {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    const response = await api.post('/auth/verify-email', {}, {
      headers: {
        'Authorization': `Bearer ${session.access_token}`
      }
    });

    console.log('Verification email sent:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error sending verification email:', error);
    throw error;
  }
}
```

### Example: Delete Account

```typescript
async function deleteAccount(userId: string) {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    // Confirm with user first!
    const confirmed = await Alert.alert(
      'Delete Account',
      'Are you sure you want to delete your account? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: async () => {
          const response = await api.delete(`/auth/users/${userId}`, {
            headers: {
              'Authorization': `Bearer ${session.access_token}`
            }
          });

          console.log('Account deleted:', response.data);
          
          // Log out and redirect to login
          await supabase.auth.signOut();
          navigation.navigate('Login');
        }}
      ]
    );
  } catch (error) {
    console.error('Error deleting account:', error);
    throw error;
  }
}
```

---

## Security Considerations

1. **Password Requirements:**
   - Minimum 8 characters
   - Consider enforcing complexity requirements in frontend

2. **Email Changes:**
   - Supabase may require email confirmation for email changes
   - Users should verify both old and new email addresses

3. **Account Deletion:**
   - Always confirm with user before deletion
   - Consider soft deletion (marking as inactive) instead of hard deletion
   - Implement a grace period for account recovery

4. **Token Management:**
   - Tokens should be stored securely (SecureStore on mobile)
   - Refresh tokens before they expire
   - Clear tokens on logout

5. **Rate Limiting:**
   - Consider implementing rate limiting for sensitive operations
   - Especially for password changes and email verification

---

## Next Steps

1. **Implement in Frontend:**
   - Add profile editing screen
   - Add password change screen
   - Add email verification button
   - Add account deletion with confirmation

2. **Add Validation:**
   - Frontend validation for email format
   - Password strength indicator
   - Confirm password field

3. **Add Features:**
   - Password reset via email
   - Two-factor authentication
   - Session management (view and revoke sessions)
   - Profile picture upload

4. **Monitoring:**
   - Log all account modifications
   - Alert on suspicious activities
   - Track failed authentication attempts

---

## API Summary

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/v1/auth/me` | GET | ✅ | Get current user profile |
| `/api/v1/auth/me` | PUT | ✅ | Update user profile |
| `/api/v1/auth/change-password` | POST | ✅ | Change password |
| `/api/v1/auth/verify-email` | POST | ✅ | Send verification email |
| `/api/v1/auth/users/{user_id}` | DELETE | ✅ | Delete user account |

---

**Status:** ✅ All endpoints implemented and ready for testing!
