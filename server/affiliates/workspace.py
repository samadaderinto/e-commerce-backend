"""Scoped referral workspaces for customers and backoffice operators."""
from typing import Any

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from affiliates.models import Marketer, Referral
from affiliates.services import MAX_REWARDED_REFERRALS, REFERRAL_REWARD_AMOUNT
from core.access import IsBackoffice
from core.listing_filters import ListingQuerySerializer, filter_records, record_page


class WorkspaceReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referral
        fields = ['id', 'status', 'reward_amount', 'created']
        read_only_fields = fields


class AffiliateOperatorSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    referral_count = serializers.IntegerField(read_only=True)
    rewarded_count = serializers.IntegerField(read_only=True)
    credit_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, allow_null=True)

    class Meta:
        model = Marketer
        fields = ['id', 'user', 'name', 'email', 'marketer_id', 'is_active', 'referral_count', 'rewarded_count', 'credit_earned', 'created']
        read_only_fields = fields


class AdminReferralReferredUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField(allow_blank=True, default='')
    last_name = serializers.CharField(allow_blank=True, default='')


class AdminReferralMarketerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    marketer_id = serializers.CharField()
    email = serializers.EmailField(source='user.email')


class AdminReferralSerializer(serializers.ModelSerializer):
    referred_user = AdminReferralReferredUserSerializer(read_only=True)
    marketer = AdminReferralMarketerSerializer(read_only=True)
    reward_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    wallet_transaction_id = serializers.IntegerField(source='wallet_transaction.id', allow_null=True, read_only=True)

    class Meta:
        model = Referral
        fields = ['id', 'marketer', 'referred_user', 'status', 'reward_amount', 'wallet_transaction_id', 'created']
        read_only_fields = fields


class AffiliateSummarySerializer(serializers.Serializer):
    total_affiliates = serializers.IntegerField()
    total_referrals = serializers.IntegerField()
    rewarded_referrals = serializers.IntegerField()
    pending_referrals = serializers.IntegerField()
    total_credit_awarded = serializers.DecimalField(max_digits=15, decimal_places=2)


class ReferralWorkspaceSerializer(serializers.Serializer):
    enrolled = serializers.BooleanField()
    name = serializers.CharField(allow_blank=True)
    referral_code = serializers.CharField(allow_blank=True)
    invite_url = serializers.CharField(allow_blank=True)
    reward_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    max_rewards = serializers.IntegerField()
    rewarded_count = serializers.IntegerField()
    credit_earned = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()
    results = WorkspaceReferralSerializer(many=True)


class AffiliateOperatorPageSerializer(serializers.Serializer):
    summary = AffiliateSummarySerializer(required=False)
    tab = serializers.CharField(default='affiliates')
    count = serializers.IntegerField()
    results = serializers.ListField()


class AffiliateOperatorQuerySerializer(ListingQuerySerializer):
    tab = serializers.ChoiceField(choices=['affiliates', 'referrals'], default='affiliates', required=False)


class ReferralWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=[ListingQuerySerializer], responses=ReferralWorkspaceSerializer)
    def get(self, request: Request) -> Response:
        marketer = Marketer.objects.filter(user=request.user).first()
        referrals = Referral.objects.filter(marketer=marketer) if marketer else Referral.objects.none()
        rewarded = referrals.filter(status=Referral.REWARDED)
        totals = rewarded.aggregate(total=Sum('reward_amount'))
        records = filter_records(
            referrals, request.query_params,
            search_fields=('id',), fields={'status': 'status'}, amount_field='reward_amount',
        ).order_by('-created', '-pk')
        count, page = record_page(records, request.query_params)
        data: dict[str, Any] = {
            'enrolled': marketer is not None,
            'name': marketer.name if marketer else '',
            'referral_code': marketer.marketer_id if marketer else '',
            'invite_url': f'{settings.FRONTEND_URL.rstrip("/")}/register?ref={marketer.marketer_id}' if marketer else '',
            'reward_amount': REFERRAL_REWARD_AMOUNT,
            'max_rewards': MAX_REWARDED_REFERRALS,
            'rewarded_count': rewarded.count(),
            'credit_earned': totals['total'] or 0,
            'count': count,
            'results': page,
        }
        return Response(ReferralWorkspaceSerializer(data).data)


class AffiliateOperatorView(APIView):
    permission_classes = [IsBackoffice]

    @extend_schema(parameters=[AffiliateOperatorQuerySerializer], responses=AffiliateOperatorPageSerializer)
    def get(self, request: Request) -> Response:
        tab = request.query_params.get('tab', 'affiliates')
        if tab == 'referrals':
            referrals = Referral.objects.select_related('referred_user', 'marketer__user', 'wallet_transaction')
            records = filter_records(
                referrals,
                request.query_params,
                search_fields=(
                    'referred_user__email',
                    'referred_user__first_name',
                    'referred_user__last_name',
                    'marketer__name',
                    'marketer__marketer_id',
                    'marketer__user__email',
                ),
                fields={'status': 'status'},
                amount_field='reward_amount',
            ).order_by('-created', '-pk')
            count, page = record_page(records, request.query_params)
            results_data = AdminReferralSerializer(page, many=True).data
        else:
            tab = 'affiliates'
            records = Marketer.objects.select_related('user').annotate(
                referral_count=Count('referrals'),
                rewarded_count=Count('referrals', filter=Q(referrals__status=Referral.REWARDED)),
                credit_earned=Coalesce(Sum('referrals__reward_amount', filter=Q(referrals__status=Referral.REWARDED)), REFERRAL_REWARD_AMOUNT * 0),
            )
            records = filter_records(
                records, request.query_params,
                search_fields=('name', 'marketer_id', 'user__email'),
                amount_field='credit_earned',
            ).order_by('-created', '-pk')
            is_active_val = request.query_params.get('is_active')
            if is_active_val in ('true', 'false'):
                records = records.filter(user__is_active=(is_active_val == 'true'))
            count, page = record_page(records, request.query_params)
            results_data = AffiliateOperatorSerializer(page, many=True).data

        rewarded_qs = Referral.objects.filter(status=Referral.REWARDED)
        summary = {
            'total_affiliates': Marketer.objects.count(),
            'total_referrals': Referral.objects.count(),
            'rewarded_referrals': rewarded_qs.count(),
            'pending_referrals': Referral.objects.filter(status=Referral.PENDING).count(),
            'total_credit_awarded': format(
                rewarded_qs.aggregate(total=Sum('reward_amount'))['total'] or 0,
                '.2f',
            ),
        }

        return Response(AffiliateOperatorPageSerializer({
            'summary': summary,
            'tab': tab,
            'count': count,
            'results': results_data,
        }).data)
