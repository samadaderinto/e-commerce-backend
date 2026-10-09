from urllib.parse import quote

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from affiliates.models import AffiliateWallet, Marketer, Referral, Url
from affiliates.serializers import (
    AffiliateWalletSerializer,
    MarketerSerializer,
    ReferralSerializer,
    AffiliateLinkRequestSerializer, UrlSerializer,
)
from product.models import Product


class AffiliatesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["redirect_url", "clickbank_outbound"]:
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["post"], url_path="register")
    def create_marketer(self, request):
        marketer = Marketer.objects.filter(user=request.user).first()
        created = marketer is None
        serializer = MarketerSerializer(
            marketer,
            data=request.data,
            partial=bool(marketer),
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        marketer = serializer.save(user=request.user)
        AffiliateWallet.objects.get_or_create(user=request.user)
        if created:
            from utils.functions import send_mail
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
            referral_link = f"{frontend_url}/?ref={marketer.marketer_id}"
            send_mail(
                "affiliate",
                request.user.email,
                {
                    "firstname": request.user.first_name,
                    "referral_code": marketer.marketer_id,
                    "referral_link": referral_link,
                    "subject": "Welcome to the ProAce Affiliate Partner Program",
                },
            )
        return Response(
            MarketerSerializer(marketer).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="me")
    def get_marketer(self, request):
        marketer = get_object_or_404(Marketer, user=request.user)
        return Response(MarketerSerializer(marketer).data)

    @action(detail=False, methods=["get"], url_path="wallet")
    def wallet(self, request):
        wallet, _ = AffiliateWallet.objects.get_or_create(user=request.user)
        return Response(AffiliateWalletSerializer(wallet).data)

    @action(detail=False, methods=["get"], url_path="referrals")
    def referrals(self, request):
        marketer = get_object_or_404(Marketer, user=request.user)
        referrals = Referral.objects.filter(marketer=marketer).select_related(
            "referred_user"
        )
        return Response(ReferralSerializer(referrals, many=True).data)

    @action(detail=False, methods=["post"], url_path="links")
    @extend_schema(request=AffiliateLinkRequestSerializer, responses=UrlSerializer)
    def create_link(self, request: Request) -> Response:
        marketer = get_object_or_404(Marketer, user=request.user)
        serializer = AffiliateLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=serializer.validated_data["product"])
        identifier = (
            serializer.validated_data.get("identifier") or f"product-{product.pk}"
        )
        url, _ = Url.objects.get_or_create(
            marketer=marketer,
            product=product,
            identifier=identifier,
            defaults={"abs_url": ""},
        )
        url.abs_url = (
            f"{settings.FRONTEND_URL.rstrip('/')}/api/affiliates/r/"
            f"{quote(marketer.marketer_id, safe='')}/{product.pk}/{quote(identifier, safe='')}/"
        )
        url.active = True
        url.save(update_fields=["abs_url", "active", "updated"])
        return Response(UrlSerializer(url).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"r/(?P<marketer_id>[^/.]+)/(?P<product_id>[^/.]+)/(?P<identifier>[^/.]+)",
    )
    @transaction.atomic
    def redirect_url(self, request, marketer_id=None, product_id=None, identifier=None):
        url = get_object_or_404(
            Url.objects.select_for_update(),
            marketer__marketer_id=marketer_id,
            product_id=product_id,
            identifier=identifier,
            active=True,
        )
        from affiliates.models import Redirect
        from django.db.models import F
        from django.utils import timezone
        from nanoid import generate

        click = Redirect.objects.filter(urlId=url).order_by('pk').first()
        if click is None:
            click = Redirect.objects.create(
                urlId=url,
                product_url=f"/products/{url.product_id}/",
                refferal_url=generate(size=15),
            )

        Redirect.objects.filter(pk=click.pk).update(
            click_rate=F('click_rate') + 1,
            last_clicked_at=timezone.now(),
            updated=timezone.now(),
        )
        return redirect(f"/products/{url.product_id}/", permanent=False)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"clickbank/outbound/(?P<product_id>[^/.]+)",
    )
    def clickbank_outbound(self, request, product_id=None):
        import os
        from urllib.parse import urlencode, parse_qs, urlsplit, urlunsplit
        from nanoid import generate
        from affiliates.models import ClickBankOutboundClick

        product = get_object_or_404(Product, pk=product_id, visibility=True)
        if product.product_type != 'affiliate_clickbank' or not product.affiliate_hoplink:
            return redirect(f"/products/{product.pk}/", permanent=False)

        # Do not route outbound traffic for unverified or blocked stores
        if product.store.status != 'active':
            return redirect(f"/products/{product.pk}/", permanent=False)

        # Validate URL scheme to prevent open redirect vulnerabilities
        split_url = urlsplit(product.affiliate_hoplink)
        if split_url.scheme not in ('http', 'https') or not split_url.netloc:
            return redirect(f"/products/{product.pk}/", permanent=False)

        user = request.user if request.user.is_authenticated else None
        user_prefix = f"u{user.id}" if user else "guest"
        tid = f"cb_{user_prefix}_{generate(size=10)}"

        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Construct target hoplink with tid and ensure ProAce affiliate nickname
        query_dict = parse_qs(split_url.query)
        if 'affiliate' not in query_dict:
            aff_nick = getattr(settings, 'CLICKBANK_AFFILIATE_NICKNAME', 'proace')
            if aff_nick:
                query_dict['affiliate'] = [aff_nick]
        query_dict['tid'] = [tid]
        flat_query = {k: v[0] for k, v in query_dict.items()}
        target_url = urlunsplit((
            split_url.scheme,
            split_url.netloc,
            split_url.path,
            urlencode(flat_query),
            split_url.fragment,
        ))

        ClickBankOutboundClick.objects.create(
            product=product,
            user=user,
            tracking_id=tid,
            hoplink_used=target_url,
            ip_address=ip if ip else None,
            user_agent=user_agent,
        )

        return redirect(target_url, permanent=False)

