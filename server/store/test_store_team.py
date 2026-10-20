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


@pytest.mark.django_db
class TestStoreTeamInvitations:
    def test_invite_unregistered_email_creates_pending_member(self, store, owner):
        client = APIClient()
        client.force_authenticate(user=owner)

        unregistered_email = "newinvitee@test.local"
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": unregistered_email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["email"] == unregistered_email
        assert res.data["status"] == StoreTeamMember.STATUS_PENDING
        assert res.data["status_display"] == "Pending Invitation"

        member = StoreTeamMember.objects.get(pk=res.data["id"])
        assert member.user is None
        assert member.invited_email == unregistered_email
        assert member.status == StoreTeamMember.STATUS_PENDING
        assert member.invite_token is not None
        assert len(member.invite_token) > 20

    def test_duplicate_pending_invite_rejected(self, store, owner):
        client = APIClient()
        client.force_authenticate(user=owner)

        unregistered_email = "duplicate@test.local"
        res1 = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": unregistered_email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": unregistered_email, "role": StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST},
            format="json",
        )
        assert res2.status_code == status.HTTP_400_BAD_REQUEST
        assert "invitation is already pending" in str(res2.data).lower()

    def test_resend_pending_invitation(self, store, owner, catalog_member):
        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Invite unregistered email
        unregistered_email = "resendme@test.local"
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": unregistered_email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        member_id = res.data["id"]

        # 2. Resend invite
        resend_res = client.post(f"/api/v1/stores/{store.pk}/team/{member_id}/resend/")
        assert resend_res.status_code == status.HTTP_200_OK
        assert "resent" in resend_res.data["detail"].lower()

        # 3. Resend for active member returns 400
        active_res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": catalog_member.email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        active_id = active_res.data["id"]
        resend_active = client.post(f"/api/v1/stores/{store.pk}/team/{active_id}/resend/")
        assert resend_active.status_code == status.HTTP_400_BAD_REQUEST

    def test_auto_linking_pending_invite_on_user_creation_and_access(self, store, owner):
        client = APIClient()
        client.force_authenticate(user=owner)

        invited_email = "soonregistered@test.local"
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": invited_email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        member_id = res.data["id"]

        # User registers with that email
        new_user = User.objects.create_user(
            email=invited_email,
            password="NewPassword123!",
            first_name="Soon",
            last_name="Registered",
        )

        # Now when the new user interacts with store endpoints, auto-linking links and activates the membership
        user_client = APIClient()
        user_client.force_authenticate(user=new_user)
        stores_res = user_client.get("/api/v1/stores/")
        assert stores_res.status_code == status.HTTP_200_OK
        store_entry = next((s for s in stores_res.data["results"] if s["id"] == store.pk), None)
        assert store_entry is not None
        assert store_entry["user_role"] == StoreTeamMember.ROLE_CATALOG_MANAGER

        # Verify membership in DB is now active and user is set
        member = StoreTeamMember.objects.get(pk=member_id)
        assert member.user == new_user
        assert member.status == StoreTeamMember.STATUS_ACTIVE
        assert member.email == invited_email

    def test_revoke_pending_invitation(self, store, owner):
        client = APIClient()
        client.force_authenticate(user=owner)

        unregistered_email = "revokeme@test.local"
        res = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": unregistered_email, "role": StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST},
            format="json",
        )
        member_id = res.data["id"]
        assert StoreTeamMember.objects.filter(pk=member_id).exists()

        delete_res = client.delete(f"/api/v1/stores/{store.pk}/team/{member_id}/")
        assert delete_res.status_code == status.HTTP_204_NO_CONTENT
        assert not StoreTeamMember.objects.filter(pk=member_id).exists()


@pytest.mark.django_db
class TestOfficialStoreTeamDelegation:
    @pytest.fixture
    def superuser_admin(self, db):
        return User.objects.create_superuser(
            email="root.admin@test.local",
            password="AdminPassword123!",
            first_name="Root",
            last_name="Admin",
        )

    @pytest.fixture
    def staff_operator(self, db):
        return User.objects.create_staffuser(
            email="staff.operator@test.local",
            password="StaffPassword123!",
            first_name="Staff",
            last_name="Operator",
        )

    @pytest.fixture
    def official_store(self, superuser_admin):
        s = Store.objects.create(
            user=superuser_admin,
            name="ProAce Official Store",
            username="proace-official",
            is_official=True,
            status=Store.STATUS_ACTIVE,
        )
        StoreAddress.objects.create(
            store=s,
            address="100 Headquarters Way",
            city="San Francisco",
            state="CA",
            country="US",
            zip="94105",
            is_default=True,
        )
        return s

    def test_staff_cannot_access_official_store_without_team_membership(
        self, official_store, superuser_admin, staff_operator
    ):
        staff_client = APIClient()
        staff_client.force_authenticate(user=staff_operator)

        # 1. Official store does not appear in staff's store listing
        res = staff_client.get("/api/v1/stores/")
        assert res.status_code == status.HTTP_200_OK
        assert not any(s["id"] == official_store.pk for s in res.data["results"])

        # 2. Direct detail access returns 404
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/").status_code == status.HTTP_404_NOT_FOUND
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/products/").status_code == status.HTTP_404_NOT_FOUND
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/orders/").status_code == status.HTTP_404_NOT_FOUND
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/team/").status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_add_staff_to_official_store_via_teams(
        self, official_store, superuser_admin, staff_operator
    ):
        admin_client = APIClient()
        admin_client.force_authenticate(user=superuser_admin)

        # 1. Admin invites staff operator as catalog manager
        invite_res = admin_client.post(
            f"/api/v1/stores/{official_store.pk}/team/",
            {"email": staff_operator.email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
            format="json",
        )
        assert invite_res.status_code == status.HTTP_201_CREATED
        assert invite_res.data["email"] == staff_operator.email
        assert invite_res.data["role"] == StoreTeamMember.ROLE_CATALOG_MANAGER
        member_id = invite_res.data["id"]

        # 2. Staff now sees the official store in their merchant listing with catalog_manager role
        staff_client = APIClient()
        staff_client.force_authenticate(user=staff_operator)
        stores_res = staff_client.get("/api/v1/stores/")
        assert stores_res.status_code == status.HTTP_200_OK
        store_entry = next((s for s in stores_res.data["results"] if s["id"] == official_store.pk), None)
        assert store_entry is not None
        assert store_entry["user_role"] == StoreTeamMember.ROLE_CATALOG_MANAGER

        # 3. Staff can create and manage products on the official store
        product_res = staff_client.post(
            f"/api/v1/stores/{official_store.pk}/products/",
            {
                "title": "Official Flagship Cap",
                "description": "High quality official company gear.",
                "price": "35.00",
                "available": 50,
                "category": "sports",
                "weight": "0.50",
                "length": "8.0",
                "width": "6.0",
                "height": "4.0",
            },
            format="json",
        )
        assert product_res.status_code == status.HTTP_201_CREATED

        # 4. Catalog manager CANNOT access orders, team, or financials
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/orders/").status_code == status.HTTP_403_FORBIDDEN
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/team/").status_code == status.HTTP_403_FORBIDDEN
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/payouts/").status_code == status.HTTP_403_FORBIDDEN

        # 5. When admin removes staff from the official store team, staff access is revoked
        remove_res = admin_client.delete(f"/api/v1/stores/{official_store.pk}/team/{member_id}/")
        assert remove_res.status_code == status.HTTP_204_NO_CONTENT

        # Staff can no longer access the official store
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/").status_code == status.HTTP_404_NOT_FOUND
        assert staff_client.get(f"/api/v1/stores/{official_store.pk}/products/").status_code == status.HTTP_404_NOT_FOUND


