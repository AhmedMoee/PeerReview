from django.test import TestCase
from django.contrib.auth.models import User
from .models import Project, Upload, JoinRequest, Message
# Create your tests here.

class ProjectModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.project = Project.objects.create(name='Test Project', owner=self.user)

    def test_project_creation(self):
        self.assertEqual(self.project.name, 'Test Project')
        self.assertEqual(self.project.owner, self.user)
        self.assertIsNotNone(self.project.created_at)

    def test_string_representation(self):
        self.assertEqual(str(self.project), 'Test Project')

    def test_add_member(self):
        member = User.objects.create(username='memberuser')
        self.project.members.add(member)
        self.assertIn(member, self.project.members.all())

class UploadModelTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(username='testuser')
        
        # Create a test project owned by the user
        self.project = Project.objects.create(name='Test Project', owner=self.user)
        
        # Create a test upload object with an owner
        self.upload = Upload.objects.create(
            name='Test File',
            file='testfile.txt',
            project=self.project,
            owner=self.user  # Add the owner field
        )

    def test_upload_creation(self):
        self.assertEqual(self.upload.name, 'Test File')
        self.assertEqual(self.upload.project, self.project)
        self.assertEqual(self.upload.owner, self.user)  # Verify the owner is set correctly
        self.assertIsNotNone(self.upload.uploaded_at)  # Ensure the uploaded_at field is populated

    def test_string_representation(self):
        # Verify that the string representation is based on the file name
        self.assertEqual(str(self.upload), 'testfile.txt')

class JoinRequestModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.project = Project.objects.create(name='Test Project', owner=self.user)
        self.join_request = JoinRequest.objects.create(user=self.user, project=self.project)

    def test_join_request_creation(self):
        self.assertEqual(self.join_request.user, self.user)
        self.assertEqual(self.join_request.project, self.project)
        self.assertEqual(self.join_request.status, 'pending')
        self.assertIsNotNone(self.join_request.created_at)

    def test_string_representation(self):
        self.assertEqual(str(self.join_request), 'testuser - Test Project (pending)')

class MessageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='testuser')
        self.project = Project.objects.create(name='Test Project', owner=self.user)
        self.message = Message.objects.create(project=self.project, user=self.user, content='Hello World')

    def test_message_creation(self):
        self.assertEqual(self.message.content, 'Hello World')
        self.assertEqual(self.message.project, self.project)
        self.assertEqual(self.message.user, self.user)
        self.assertIsNotNone(self.message.created_at)

    def test_string_representation(self):
        self.assertEqual(str(self.message.content), 'Hello World')