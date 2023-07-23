from django.test import TestCase

# Create your tests here.
import pytest


@pytest.fixture
def function_fixture():
   print('Fixture for each test')
   return 1


@pytest.fixture(scope='module')
def module_fixture():
   print('Fixture for module')
   return 2