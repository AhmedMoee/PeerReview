from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Project, Upload, JoinRequest, Message, Prompt, PromptResponse, UserProfile, ProjectMembership

# ------------------- Models Tests -------------------

class ProjectModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            description="A test project description"
        )

    def test_project_creation(self):
        self.assertEqual(self.project.name, "Test Project")
        self.assertEqual(self.project.owner.username, "testuser")
        self.assertEqual(self.project.description, "A test project description")
        self.assertEqual(self.project.upvotes, 0)

    def test_add_member_to_project(self):
        member = User.objects.create_user(username='memberuser', password='password')
        self.project.members.add(member)
        self.assertIn(member, self.project.members.all())

    def test_string_representation(self):
        self.assertEqual(str(self.project), "Test Project")


class UploadModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            description="A test project description"
        )
        self.upload = Upload.objects.create(
            name="Test File",
            owner=self.user,
            project=self.project,
            file="testfile.txt"
        )

    def test_upload_creation(self):
        self.assertEqual(self.upload.name, "Test File")
        self.assertEqual(self.upload.owner.username, "testuser")
        self.assertEqual(self.upload.project.name, "Test Project")

    def test_string_representation(self):
        self.assertEqual(str(self.upload), "testfile.txt")


class JoinRequestModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            description="A test project description"
        )
        self.join_request = JoinRequest.objects.create(
            user=self.user,
            project=self.project,
            status='pending'
        )

    def test_join_request_creation(self):
        self.assertEqual(self.join_request.status, 'pending')
        self.assertEqual(self.join_request.user.username, 'testuser')

    def test_string_representation(self):
        expected_str = f"{self.join_request.user.username} - {self.join_request.project.name} (pending)"
        self.assertEqual(str(self.join_request), expected_str)


class MessageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            description="A test project description"
        )
        self.message = Message.objects.create(
            project=self.project,
            user=self.user,
            content="This is a test message."
        )

    def test_message_creation(self):
        self.assertEqual(self.message.content, "This is a test message.")
        self.assertEqual(self.message.user.username, "testuser")


class PromptAndResponseModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(
            name="Test Project",
            owner=self.user,
            description="A test project description"
        )
        self.upload = Upload.objects.create(
            name="Test File",
            owner=self.user,
            project=self.project,
            file="testfile.txt"
        )

    def test_create_prompt_and_response(self):
        prompt = Prompt.objects.create(
            upload=self.upload,
            content="What is the purpose of this file?",
            created_by=self.user
        )
        
        response = PromptResponse.objects.create(
            prompt=prompt,
            content="This file is for testing purposes.",
            created_by=self.user
        )

        # Check if prompt and response were created successfully
        prompt_exists = Prompt.objects.filter(content="What is the purpose of this file?").exists()
        response_exists = PromptResponse.objects.filter(content="This file is for testing purposes.").exists()
        
        self.assertTrue(prompt_exists)
        self.assertTrue(response_exists)


# ------------------- Views Tests -------------------

class DashboardViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    

    def test_dashboard_authenticated_user_shows_projects(self):
        # Log in user
        self.client.login(username='testuser', password='password')

        # Create a project owned by the user
        Project.objects.create(name="User's Project", owner=self.user)
        
        response = self.client.get(reverse('dashboard'))
        
        # Check if the dashboard renders with the user's projects
        self.assertEqual(response.status_code, 200)


class CreateProjectViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_create_project_get_request(self):
        # Log in user
        self.client.login(username='testuser', password='password')

        response = self.client.get(reverse('create_project'))
        
        # Ensure the form loads successfully
        self.assertEqual(response.status_code, 200)

    
        

class JoinRequestViewTest(TestCase):
    def setUp(self):
        # Create users and a project
        self.owner = User.objects.create_user(username='owner', password='password')
        self.requester = User.objects.create_user(username='requester', password='password')
        
    def test_request_to_join_creates_join_request(self):
       # Log in as requester and submit a join request
       pass  # Add implementation here


# Additional tests can be added similarly.