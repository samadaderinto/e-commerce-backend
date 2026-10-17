import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.exceptions import ValidationError

from store.models import Store, StoreTeamMember, StoreAddress
from product.models import Product

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@test.local",
        password="TestPassword123!",
        first_name="Store",
        last_name="Owner",
    )


@pytest.fixture
def admin_member(db):
    return User.objects.create_user(
        email="admin_member@test.local",
        password="TestPassword123!",
        first_name="Admin",
        last_name="Member",
    )


@pytest.fixture
def catalog_member(db):
    return User.objects.create_user(
        email="catalog_member@test.local",
        password="TestPassword123!",
        first_name="Catalog",
        last_name="Manager",
    )


@pytest.fixture
def fulfillment_member(db):
    return User.objects.create_user(
        email="fulfillment_member@test.local",
        password="TestPassword123!",
        first_name="Fulfillment",
        last_name="Specialist",
    )


@pytest.fixture
def outsider(db):
    return User.objects.create_user(
        email="outsider@test.local",
        password="TestPassword123!",
        first_name="Outside",
        last_name="User",
    )


@pytest.fixture
def store(owner):
    s = Store.objects.create(
        user=owner,
        name="Apex Athletics",
        status=Store.STATUS_ACTIVE,
    )
    StoreAddress.objects.create(
        store=s,
        address="123 Main St",
        city="Austin",
        state="TX",
        country="US",
        zip="78701",
        is_default=True,
    )
    return s


@pytest.fixture
def sample_product(store):
    return Product.objects.create(
        store=store,
        title="Training Shoes",
        price=Decimal("120.00"),
        discount=0,
        available=10,
        visibility=True,
    )


@pytest.mark.django_db
class TestStoreTeamMemberModel:
    def test_owner_cannot_be_team_member_of_own_store(self, store, owner):
        member = StoreTeamMember(
            store=store,
            user=owner,
            role=StoreTeamMember.ROLE_STORE_ADMIN,
        )
        with pytest.raises(ValidationError) as exc:
            member.clean()
        assert "Store owners cannot be added as team members" in str(exc.value)

    def test_unique_store_user_membership(self, store, catalog_member):
        StoreTeamMember.objects.create(
            store=store,
            user=catalog_member,
            role=StoreTeamMember.ROLE_CATALOG_MANAGER,
        )
        duplicate = StoreTeamMember(
            store=store,
            user=catalog_member,
            role=StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST,
        )
        with pytest.raises(Exception):
            duplicate.save()


@pytest.mark.django_db
class TestStoreTeamEndpoints:
    def test_owner_can_list_and_invite_team_members(self, store, owner, catalog_member, admin_member):
        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Invite catalog manager
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": catalog_member.email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["email"] == catalog_member.email
        assert res.data["role"] == StoreTeamMember.ROLE_CATALOG_MANAGER
        member_id = res.data["id"]

        # 2. List team
        res = client.get(f"/api/v1/stores/{store.pk}/team/")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 1

        # 3. Update role
        res = client.patch(
            f"/api/v1/stores/{store.pk}/team/{member_id}/",
            {"role": StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["role"] == StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST

        # 4. Remove member
        res = client.delete(f"/api/v1/stores/{store.pk}/team/{member_id}/")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert StoreTeamMember.objects.filter(pk=member_id).count() == 0

    def test_store_admin_permissions(self, store, owner, admin_member, catalog_member, fulfillment_member):
        StoreTeamMember.objects.create(
            store=store,
            user=admin_member,
            role=StoreTeamMember.ROLE_STORE_ADMIN,
        )

        client = APIClient()
        client.force_authenticate(user=admin_member)

        # Store admin can invite a catalog manager
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": catalog_member.email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        # Store admin CANNOT invite another Store Admin
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": fulfillment_member.email, "role": StoreTeamMember.ROLE_STORE_ADMIN},
            format="json",
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRoleScopedPermissions:
    def test_catalog_manager_can_manage_products_but_not_orders(self, store, catalog_member, sample_product):
        StoreTeamMember.objects.create(
            store=store,
            user=catalog_member,
            role=StoreTeamMember.ROLE_CATALOG_MANAGER,
        )

        client = APIClient()
        client.force_authenticate(user=catalog_member)

        # 1. Store list includes the store with user_role == 'catalog_manager'
        res = client.get("/api/v1/stores/")
        assert res.status_code == status.HTTP_200_OK
        store_entry = next((s for s in res.data["results"] if s["id"] == store.pk), None)
        assert store_entry is not None
        assert store_entry["user_role"] == StoreTeamMember.ROLE_CATALOG_MANAGER

        # 2. Can list products
        res = client.get(f"/api/v1/stores/{store.pk}/products/")
        assert res.status_code == status.HTTP_200_OK

        # 3. Can update products
        res = client.patch(
            f"/api/v1/stores/{store.pk}/products/{sample_product.pk}/",
            {"price": "135.00"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK

        # 4. CANNOT view orders
        res = client.get(f"/api/v1/stores/{store.pk}/orders/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 5. CANNOT view payouts
        res = client.get(f"/api/v1/stores/{store.pk}/payouts/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 6. CANNOT view team
        res = client.get(f"/api/v1/stores/{store.pk}/team/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_fulfillment_specialist_can_manage_orders_but_not_products(self, store, fulfillment_member, sample_product):
        StoreTeamMember.objects.create(
            store=store,
            user=fulfillment_member,
            role=StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST,
        )

        client = APIClient()
        client.force_authenticate(user=fulfillment_member)

        # 1. Store list includes the store with user_role == 'fulfillment_specialist'
        res = client.get("/api/v1/stores/")
        assert res.status_code == status.HTTP_200_OK
        store_entry = next((s for s in res.data["results"] if s["id"] == store.pk), None)
        assert store_entry is not None
        assert store_entry["user_role"] == StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST

        # 2. Can view orders
        res = client.get(f"/api/v1/stores/{store.pk}/orders/")
        assert res.status_code == status.HTTP_200_OK

        # 3. CANNOT list or manage products
        res = client.get(f"/api/v1/stores/{store.pk}/products/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 4. CANNOT create products
        res = client.post(
            f"/api/v1/stores/{store.pk}/products/",
            {"title": "Sneakers", "price": "99.00", "available": 5},
            format="json",
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # 5. CANNOT view payouts or team
        res = client.get(f"/api/v1/stores/{store.pk}/payouts/")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        res = client.get(f"/api/v1/stores/{store.pk}/team/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_access_store(self, store, outsider):
        client = APIClient()
        client.force_authenticate(user=outsider)

        # Store does not appear in store list
        res = client.get("/api/v1/stores/")
        assert res.status_code == status.HTTP_200_OK
        assert not any(s["id"] == store.pk for s in res.data["results"])

        # Direct access returns 404
        res = client.get(f"/api/v1/stores/{store.pk}/products/")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        res = client.get(f"/api/v1/stores/{store.pk}/orders/")
        assert res.status_code == status.HTTP_404_NOT_FOUND
