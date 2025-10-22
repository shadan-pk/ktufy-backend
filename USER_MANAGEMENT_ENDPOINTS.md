# User Management Endpoints Documentation

## Overview
These endpoints allow users to manage their profiles, request password resets, verify emails, and delete accounts.

**Important**: All profile data is stored in the `public.users` table, while authentication data (email, password) is managed by Supabase in the `auth.users` table.

## Base URL
```
http://localhost:8000/api/v1/auth
```

---

## Database Structure

### public.users Table
Stores user profile information:
- `id` (uuid) - User ID from auth.users
- `name` - Full name
- `email` - Email address (synced with auth.users)
- `registration_number` - University registration number
- `college` - College name
- `branch` - Branch/Department
- `year_joined` - Year of joining
- `year_ending` - Year of completion
- `roll_number` - Roll number
- `metadata` (jsonb) - Additional metadata
- `created_at` - Timestamp

### auth.users Table
Managed by Supabase for authentication (email, password, etc.)

---

## Endpoints

### 1. ✅ GET /api/v1/auth/me
**Get Current User Profile**

Get the authenticated user's profile information from public.users table.

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
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "John Doe",
    "email": "student@ktu.edu.in",
    "registration_number": "KTU123456",
    "college": "College of Engineering Trivandrum",
    "branch": "Computer Science",
    "year_joined": 2021,
    "year_ending": 2025,
    "roll_number": "CSE21001",
    "metadata": {
      "phone": "+91-1234567890",
      "semester": 5
    },
    "created_at": "2025-10-20T10:30:00Z"
  }
}
```

---

### 2. ✨ PUT /api/v1/auth/me
**Update User Profile**

Update the authenticated user's profile in the public.users table and optionally email in auth.users.

**Authentication Required**: Yes (Bearer token)

**Request Body (all fields optional):**
```json
{
  "email": "newemail@ktu.edu.in",         // Updates both tables
  "name": "Updated Name",                  // public.users
  "registration_number": "KTU123456",      // public.users
  "college": "College of Engineering",     // public.users
  "branch": "Computer Science",            // public.users
  "year_joined": 2021,                     // public.users
  "year_ending": 2025,                     // public.users
  "roll_number": "CSE21001",              // public.users
  "metadata": {                            // public.users JSONB
    "phone": "+91-1234567890",
    "semester": 5
  }
}
```

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "branch": "Computer Science",
    "year_joined": 2021,
    "metadata": {
      "phone": "+91-1234567890",
      "semester": 5
    }
  }'
```

**Response (200 OK):**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "student@ktu.edu.in",
  "role": "authenticated",
  "metadata": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Updated Name",
    "email": "student@ktu.edu.in",
    "registration_number": "KTU123456",
    "college": "College of Engineering Trivandrum",
    "branch": "Computer Science",
    "year_joined": 2021,
    "year_ending": 2025,
    "roll_number": "CSE21001",
    "metadata": {
      "phone": "+91-1234567890",
      "semester": 5
    }
  }
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "No update data provided"
}
```

---

### 3. 🔐 POST /api/v1/auth/request-password-reset
**Request Password Reset**

Request a password reset email via Supabase (uses Supabase's built-in password reset).

**No authentication required** (public endpoint)

**Request Body:**
```json
{
  "email": "student@ktu.edu.in"
}
```

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/request-password-reset" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@ktu.edu.in"
  }'
```

**Response (200 OK):**
```json
{
  "message": "If the email exists, a password reset link has been sent",
  "success": true
}
```

**Note**: For security, this endpoint always returns success, even if the email doesn't exist. This prevents email enumeration attacks.

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

async function updateUserProfile(profileData: any) {
  try {
    // Get current session
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    // Call backend endpoint to update public.users table
    const response = await api.put('/auth/me', profileData, {
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

// Usage - Update any combination of fields
updateUserProfile({
  name: 'John Doe',
  registration_number: 'KTU123456',
  college: 'College of Engineering Trivandrum',
  branch: 'Computer Science',
  year_joined: 2021,
  year_ending: 2025,
  roll_number: 'CSE21001',
  metadata: {
    phone: '+91-1234567890',
    semester: 5
  }
});
```

### Example: Request Password Reset

```typescript
async function requestPasswordReset(email: string) {
  try {
    // Public endpoint - no authentication needed
    const response = await api.post('/auth/request-password-reset', {
      email: email
    });

    console.log('Password reset requested:', response.data);
    Alert.alert('Success', 'Password reset link sent to your email');
    return response.data;
  } catch (error) {
    console.error('Error requesting password reset:', error);
    Alert.alert('Error', 'Failed to send password reset email');
    throw error;
  }
}

// Or use Supabase directly (recommended)
async function requestPasswordResetSupabase(email: string) {
  try {
    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: 'yourapp://reset-password'
    });
    Alert.alert('Success', 'Password reset link sent to your email');
  } catch (error) {
    console.error('Error:', error);
    Alert.alert('Error', 'Failed to send password reset email');
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
| `/api/v1/auth/me` | GET | ✅ | Get current user profile from public.users |
| `/api/v1/auth/me` | PUT | ✅ | Update user profile in public.users |
| `/api/v1/auth/request-password-reset` | POST | ❌ | Request password reset via Supabase |
| `/api/v1/auth/verify-email` | POST | ✅ | Send verification email |
| `/api/v1/auth/users/{user_id}` | DELETE | ✅ | Delete user account |

---

## Key Changes from Original Plan

1. **✅ Password Management**: Using Supabase's built-in password reset instead of custom change-password endpoint
   - More secure (uses email verification)
   - Follows best practices
   - Prevents unauthorized password changes

2. **✅ Database Integration**: Endpoints now update `public.users` table
   - All profile fields (name, registration_number, college, branch, etc.)
   - Structured data in PostgreSQL
   - JSONB metadata for flexible additional fields

3. **✅ Email Updates**: Email changes update both `auth.users` and `public.users`
   - Keeps tables in sync
   - Supabase may require email confirmation

---

**Status:** ✅ All endpoints implemented with proper database integration!
