"""
Tests for the Mergington High School API
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from app import app, activities

client = TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        k: {**v, "participants": v["participants"].copy()}
        for k, v in activities.items()
    }
    yield
    # Restore after test
    for activity_name, activity_data in activities.items():
        activities[activity_name]["participants"] = original_activities[activity_name]["participants"].copy()


class TestActivitiesEndpoint:
    """Tests for GET /activities endpoint"""

    def test_get_activities_returns_all_activities(self):
        """Test that GET /activities returns all available activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert len(data) == 9

    def test_activities_have_required_fields(self):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        for activity_name, activity in data.items():
            assert "description" in activity
            assert "schedule" in activity
            assert "max_participants" in activity
            assert "participants" in activity
            assert isinstance(activity["participants"], list)

    def test_activities_have_participants(self):
        """Test that activities contain participant data"""
        response = client.get("/activities")
        data = response.json()
        chess_club = data["Chess Club"]
        assert len(chess_club["participants"]) > 0
        assert "michael@mergington.edu" in chess_club["participants"]


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""

    def test_signup_for_activity_success(self, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in activities["Chess Club"]["participants"]

    def test_signup_nonexistent_activity(self, reset_activities):
        """Test signup for a non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

    def test_signup_duplicate_email(self, reset_activities):
        """Test that duplicate signups are rejected"""
        # First signup
        response1 = client.post(
            "/activities/Chess Club/signup?email=michael@mergington.edu"
        )
        assert response1.status_code == 400
        assert "already signed up" in response1.json()["detail"]

    def test_signup_new_student(self, reset_activities):
        """Test signup with a new student email"""
        initial_count = len(activities["Programming Class"]["participants"])
        response = client.post(
            "/activities/Programming Class/signup?email=alice@mergington.edu"
        )
        assert response.status_code == 200
        assert len(activities["Programming Class"]["participants"]) == initial_count + 1

    def test_signup_returns_message(self, reset_activities):
        """Test that signup returns appropriate message"""
        response = client.post(
            "/activities/Art Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "test@mergington.edu" in data["message"]
        assert "Art Club" in data["message"]


class TestUnregisterEndpoint:
    """Tests for POST /activities/{activity_name}/unregister endpoint"""

    def test_unregister_success(self, reset_activities):
        """Test successful unregistration from an activity"""
        # First, ensure the student is registered
        student_email = "michael@mergington.edu"
        assert student_email in activities["Chess Club"]["participants"]
        
        # Unregister
        response = client.post(
            f"/activities/Chess Club/unregister?email={student_email}"
        )
        assert response.status_code == 200
        assert student_email not in activities["Chess Club"]["participants"]

    def test_unregister_nonexistent_activity(self, reset_activities):
        """Test unregister from a non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Club/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

    def test_unregister_unregistered_student(self, reset_activities):
        """Test that unregistering a student who isn't registered fails"""
        response = client.post(
            "/activities/Chess Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        assert "not registered" in response.json()["detail"]

    def test_unregister_returns_message(self, reset_activities):
        """Test that unregister returns appropriate message"""
        response = client.post(
            "/activities/Basketball Club/unregister?email=liam@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "liam@mergington.edu" in data["message"]
        assert "Basketball Club" in data["message"]

    def test_unregister_removes_participant(self, reset_activities):
        """Test that unregister actually removes the participant"""
        activity = activities["Drama Society"]
        student = "ethan@mergington.edu"
        initial_count = len(activity["participants"])
        
        client.post(f"/activities/Drama Society/unregister?email={student}")
        
        assert len(activity["participants"]) == initial_count - 1
        assert student not in activity["participants"]


class TestRootEndpoint:
    """Tests for GET / endpoint"""

    def test_root_redirects_to_static(self):
        """Test that root endpoint redirects to static page"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestIntegration:
    """Integration tests for signup and unregister workflows"""

    def test_signup_then_unregister(self, reset_activities):
        """Test signing up and then unregistering a student"""
        student_email = "integration@mergington.edu"
        activity = "Soccer Team"
        
        # Sign up
        signup_response = client.post(
            f"/activities/{activity}/signup?email={student_email}"
        )
        assert signup_response.status_code == 200
        assert student_email in activities[activity]["participants"]
        
        # Unregister
        unregister_response = client.post(
            f"/activities/{activity}/unregister?email={student_email}"
        )
        assert unregister_response.status_code == 200
        assert student_email not in activities[activity]["participants"]

    def test_multiple_signups_different_activities(self, reset_activities):
        """Test signing up for multiple activities"""
        student_email = "multisport@mergington.edu"
        activities_to_join = ["Chess Club", "Art Club", "Science Club"]
        
        for activity in activities_to_join:
            response = client.post(
                f"/activities/{activity}/signup?email={student_email}"
            )
            assert response.status_code == 200
        
        # Verify student is in all activities
        for activity in activities_to_join:
            assert student_email in activities[activity]["participants"]
