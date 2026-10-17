"""Owner-scoped payout destinations with encrypted account identifiers."""
import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import BankAccount, StripePayoutDestination, User


def bank_cipher() -> Fernet:
    key = hashlib.sha256(('payout-destinations:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class BankAccountSerializer(serializers.ModelSerializer):
    account_number = serializers.RegexField(r'^\d{4,34}$', write_only=True, required=False)
    routing_number = serializers.RegexField(r'^\d{4,12}$', write_only=True, required=False)
    account_last4 = serializers.CharField(read_only=True)
    routing_last4 = serializers.CharField(read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            'id', 'bank_name', 'account_holder_name', 'account_number',
            'routing_number', 'account_last4', 'routing_last4', 'is_default',
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.instance is None:
            for field in ('account_number', 'routing_number'):
                if not attrs.get(field):
                    raise serializers.ValidationError({field: 'This field is required.'})
        for field in ('account_number', 'routing_number'):
            value = attrs.pop(field, None)
            if value:
                attrs[f'{field}_encrypted'] = bank_cipher().encrypt(value.encode()).decode()
                attrs[field.replace('_number', '_last4')] = value[-4:]
        return attrs


class BankAccountQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, max_length=160)
    is_default = serializers.BooleanField(required=False)


class BankAccountsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=[BankAccountQuerySerializer], responses=BankAccountSerializer(many=True))
    def get(self, request: Request, pk: int | None = None) -> Response:
        accounts = BankAccount.objects.filter(user=request.user).order_by('-is_default', '-pk')
        query = BankAccountQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        criteria = query.validated_data
        if criteria.get('search'):
            search = criteria['search']
            accounts = accounts.filter(
                Q(bank_name__icontains=search)
                | Q(account_holder_name__icontains=search)
                | Q(account_last4__icontains=search)
            )
        if 'is_default' in request.query_params:
            # QueryDict BooleanField parsing treats an omitted checkbox as False.
            # Only filter when the caller explicitly supplies this criterion.
            accounts = accounts.filter(is_default=criteria['is_default'])
        if pk is not None:
            return Response(BankAccountSerializer(get_object_or_404(accounts, pk=pk)).data)
        return Response(BankAccountSerializer(accounts, many=True).data)

    @extend_schema(request=BankAccountSerializer, responses={201: BankAccountSerializer})
    @transaction.atomic
    def post(self, request: Request, pk: int | None = None) -> Response:
        if pk is not None:
            raise MethodNotAllowed('POST')
        return self.save_account(request, None)

    @extend_schema(request=BankAccountSerializer, responses=BankAccountSerializer)
    @transaction.atomic
    def patch(self, request: Request, pk: int | None = None) -> Response:
        if pk is None:
            raise MethodNotAllowed('PATCH')
        return self.save_account(request, pk)

    def save_account(self, request: Request, pk: int | None) -> Response:
        User.objects.select_for_update().get(pk=request.user.pk)
        accounts = BankAccount.objects.filter(user=request.user)
        instance = get_object_or_404(accounts, pk=pk) if pk is not None else None
        serializer = BankAccountSerializer(
            instance, data=request.data, partial=pk is not None,
        )
        serializer.is_valid(raise_exception=True)
        make_default = serializer.validated_data.get(
            'is_default', instance.is_default if instance else False,
        ) or not accounts.exists()
        if instance and instance.is_default and not make_default:
            raise serializers.ValidationError({'is_default': 'Set another account as default first.'})
        if make_default:
            accounts.update(is_default=False)
        account = serializer.save(user=request.user, is_default=make_default)
        return Response(BankAccountSerializer(account).data, status=200 if pk is not None else 201)

    @extend_schema(responses={204: None})
    @transaction.atomic
    def delete(self, request: Request, pk: int | None = None) -> Response:
        if pk is None:
            raise MethodNotAllowed('DELETE')
        User.objects.select_for_update().get(pk=request.user.pk)
        account = get_object_or_404(BankAccount, pk=pk, user=request.user)
        was_default = account.is_default
        account.delete()
        if was_default:
            replacement = BankAccount.objects.filter(user=request.user).order_by('pk').first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=['is_default'])
        return Response(status=204)


def payout_account_details(user: User, account_id: int) -> dict[str, str]:
    account = get_object_or_404(BankAccount, user=user, pk=account_id)
    return {
        'bank_name': account.bank_name,
        'account_holder_name': account.account_holder_name,
        'account_number': bank_cipher().decrypt(account.account_number_encrypted.encode()).decode(),
        'routing_number': bank_cipher().decrypt(account.routing_number_encrypted.encode()).decode(),
    }


class StripePayoutDestinationSerializer(serializers.ModelSerializer):
    stripe_account_id = serializers.RegexField(
        r'^acct_[A-Za-z0-9]{8,}$', write_only=True, required=False,
    )
    account_id_last4 = serializers.CharField(read_only=True)

    class Meta:
        model = StripePayoutDestination
        fields = ['id', 'label', 'stripe_account_id', 'account_id_last4', 'is_default']

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.instance is None and not attrs.get('stripe_account_id'):
            raise serializers.ValidationError({'stripe_account_id': 'This field is required.'})
        label = attrs.get('label')
        if label is not None:
            attrs['label'] = label.strip()
            if not attrs['label']:
                raise serializers.ValidationError({'label': 'Enter a name for this Stripe destination.'})
        account_id = attrs.pop('stripe_account_id', None)
        if account_id:
            attrs['account_id_encrypted'] = bank_cipher().encrypt(account_id.encode()).decode()
            attrs['account_id_last4'] = account_id[-4:]
        return attrs


class StripePayoutDestinationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StripePayoutDestinationSerializer(many=True))
    def get(self, request: Request, pk: int | None = None) -> Response:
        destinations = StripePayoutDestination.objects.filter(user=request.user).order_by('-is_default', '-pk')
        if pk is not None:
            destination = get_object_or_404(destinations, pk=pk)
            return Response(StripePayoutDestinationSerializer(destination).data)
        return Response(StripePayoutDestinationSerializer(destinations, many=True).data)

    @extend_schema(request=StripePayoutDestinationSerializer, responses={201: StripePayoutDestinationSerializer})
    @transaction.atomic
    def post(self, request: Request, pk: int | None = None) -> Response:
        if pk is not None:
            raise MethodNotAllowed('POST')
        return self.save_destination(request, None)

    @extend_schema(request=StripePayoutDestinationSerializer, responses=StripePayoutDestinationSerializer)
    @transaction.atomic
    def patch(self, request: Request, pk: int | None = None) -> Response:
        if pk is None:
            raise MethodNotAllowed('PATCH')
        return self.save_destination(request, pk)

    def save_destination(self, request: Request, pk: int | None) -> Response:
        User.objects.select_for_update().get(pk=request.user.pk)
        destinations = StripePayoutDestination.objects.filter(user=request.user)
        instance = get_object_or_404(destinations, pk=pk) if pk is not None else None
        serializer = StripePayoutDestinationSerializer(
            instance, data=request.data, partial=pk is not None,
        )
        serializer.is_valid(raise_exception=True)
        make_default = serializer.validated_data.get(
            'is_default', instance.is_default if instance else False,
        ) or not destinations.exists()
        if instance and instance.is_default and not make_default:
            raise serializers.ValidationError(
                {'is_default': 'Set another Stripe destination as default first.'},
            )
        if make_default:
            destinations.update(is_default=False)
        destination = serializer.save(user=request.user, is_default=make_default)
        return Response(
            StripePayoutDestinationSerializer(destination).data,
            status=200 if pk is not None else 201,
        )

    @extend_schema(responses={204: None})
    @transaction.atomic
    def delete(self, request: Request, pk: int | None = None) -> Response:
        if pk is None:
            raise MethodNotAllowed('DELETE')
        User.objects.select_for_update().get(pk=request.user.pk)
        destination = get_object_or_404(StripePayoutDestination, pk=pk, user=request.user)
        was_default = destination.is_default
        destination.delete()
        if was_default:
            replacement = StripePayoutDestination.objects.filter(user=request.user).order_by('pk').first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=['is_default'])
        return Response(status=204)


def stripe_payout_destination_details(user: User, destination_id: int) -> dict[str, str]:
    destination = get_object_or_404(StripePayoutDestination, user=user, pk=destination_id)
    account_id = bank_cipher().decrypt(destination.account_id_encrypted.encode()).decode()
    return {
        'destination_type': 'stripe',
        'destination': account_id,
        'destination_label': destination.label,
    }
