from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser, PasswordReset


class CustomUserTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
        )

    def test_user_creation(self):
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_superuser_creation(self):
        owner = CustomUser.objects.create_superuser(
            email='owner@example.com',
            password='ownerpass123',
        )
        self.assertTrue(owner.is_superuser)


class PasswordResetTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='oldpass123',
        )

    def test_password_reset_generation(self):
        reset = PasswordReset.objects.create(
            user=self.user,
            token=PasswordReset.generate_token(),
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self.assertFalse(reset.used)
        self.assertTrue(reset.is_valid())


class BrowserAuthFlowTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='owner@example.com',
            password='StrongPass123!',
            first_name='Owner',
            last_name='User',
        )

    def test_signup_succeeds(self):
        response = self.client.post(
            reverse('signup'),
            {
                'email': 'newuser@example.com',
                'first_name': 'New',
                'last_name': 'User',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email='newuser@example.com').exists())
        self.assertRedirects(response, reverse('dashboard_home'))

    def test_duplicate_email_is_rejected(self):
        response = self.client.post(
            reverse('signup'),
            {
                'email': 'owner@example.com',
                'first_name': 'Owner',
                'last_name': 'User',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email already exists')

    def test_valid_login_succeeds(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'owner@example.com', 'password': 'StrongPass123!'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(response, reverse('dashboard_home'))

    def test_invalid_login_fails(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'owner@example.com', 'password': 'WrongPassword!'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct email and password')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_authenticated_user_can_access_dashboard(self):
        self.client.login(username='owner@example.com', password='StrongPass123!')
        response = self.client.get(reverse('dashboard_home'))

        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard_home'))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard_home')}")

    def test_logout_invalidates_the_authenticated_session(self):
        self.client.login(username='owner@example.com', password='StrongPass123!')
        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_password_reset_flow_behaves_correctly(self):
        token = PasswordReset.generate_token()
        reset = PasswordReset.objects.create(
            user=self.user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        get_response = self.client.get(reverse('password_reset_token', args=[token]))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(
            reverse('password_reset_token', args=[token]),
            {'new_password1': 'NewStrongPass123!', 'new_password2': 'NewStrongPass123!'},
            follow=True,
        )

        self.assertEqual(post_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))
        reset.refresh_from_db()
        self.assertTrue(reset.used)

    def test_password_reset_request_view(self):
        response = self.client.post(
            reverse('password_reset_request'),
            {'email': 'owner@example.com'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PasswordReset.objects.filter(user=self.user).exists())

    def test_root_redirect(self):
        # Unauthenticated redirects to login
        res = self.client.get('/')
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('login'))

        # Authenticated redirects to dashboard
        self.client.login(username='owner@example.com', password='StrongPass123!')
        res_auth = self.client.get('/')
        self.assertEqual(res_auth.status_code, 302)
        self.assertRedirects(res_auth, reverse('dashboard_home'))


class ApiAuthTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='apiuser@example.com',
            password='ApiPass123!',
            first_name='Api',
            last_name='User',
        )

    def test_api_login_and_profile(self):
        login_resp = self.client.post(
            '/api/auth/login/',
            {'email': 'apiuser@example.com', 'password': 'ApiPass123!'},
            content_type='application/json',
        )
        self.assertEqual(login_resp.status_code, 200)
        data = login_resp.json()
        self.assertEqual(data['user']['email'], 'apiuser@example.com')

        # Test profile endpoint while logged in
        profile_resp = self.client.get('/api/auth/users/profile/')
        self.assertEqual(profile_resp.status_code, 200)
        self.assertEqual(profile_resp.json()['email'], 'apiuser@example.com')

    def test_api_signup(self):
        signup_resp = self.client.post(
            '/api/auth/signup/',
            {
                'email': 'newapiuser@example.com',
                'password': 'ApiPass123!',
                'first_name': 'New',
                'last_name': 'Api',
            },
            content_type='application/json',
        )
        self.assertEqual(signup_resp.status_code, 201)
        self.assertTrue(CustomUser.objects.filter(email='newapiuser@example.com').exists())

