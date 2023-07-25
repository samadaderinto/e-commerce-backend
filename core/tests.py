from django.urls import reverse
import pytest

from core.models import User
from rest_framework.test import APIClient




@pytest.fixture
def api_client():
    client = APIClient()
    return client



@pytest.mark.django_db
def create_user():
    payload = {
        "first_name": "samaad",
        "last_name": "ade",
        "email": "adesamad12341@gmail.com",
        "phone1": "+2349021162144",
        "gender": "male",
        "password": "jejwjheh",
        "phone2": "+12015550123"
    }
    
    user = User.objects.create_user(**payload)
    
    assert user['first_name'] == payload["first_name"]
    assert user['last_name'] == payload["last_name"]
    assert user['email'] == payload["email"]
    assert user['gender'] == payload["gender"]
    assert user['phone1'] == payload["phone1"]



    
