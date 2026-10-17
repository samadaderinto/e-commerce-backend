from urllib.parse import quote

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from django.http import HttpResponse
from rest_framework.request import Request
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from affiliates.models import AffiliateWallet, Marketer, Referral, Url
from core.access import IsCustomer
from affiliates.serializers import (
    AffiliateWalletSerializer,
    MarketerSerializer,
    ReferralSerializer,
    ReferralPageSerializer,
    AffiliateLinkRequestSerializer, UrlSerializer,
)
from core.listing_filters import ListingQuerySerializer, filter_records, record_page
from product.models import Product


class AffiliatesViewSet(viewsets.ViewSet):
    permission_classes = [IsCustomer]
    serializer_class = MarketerSerializer

    def get_permissions(self):
        if self.action in ["redirect_url", "clickbank_outbound"]:
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["post"], url_path="register")
    @transaction.atomic
    @extend_schema(request=MarketerSerializer, responses=MarketerSerializer)
    def create_marketer(self, request: Request) -> Response:
        from core.models import User

        locked_user = User.objects.select_for_update().get(pk=request.user.pk)
        marketer = Marketer.objects.filter(user=locked_user).first()
        created = marketer is None
        serializer = MarketerSerializer(
            marketer,
            data=request.data,
            partial=bool(marketer),
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        marketer = serializer.save(user=locked_user)
        AffiliateWallet.objects.get_or_create(user=locked_user)
        if created:
            from notification.views import create_notification
            create_notification(
                locked_user, "Affiliate enrollment confirmed", target=marketer,
                data={"event": "affiliate_enrolled", "email": False},
            )
            from utils.functions import send_mail
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
            referral_link = f"{frontend_url}/register?ref={marketer.marketer_id}"
            dashboard_url = f"{frontend_url}/account/affiliates"
            send_mail(
                "affiliate",
                locked_user.email,
                {
                    "firstname": locked_user.first_name,
                    "referral_code": marketer.marketer_id,
                    "referral_link": referral_link,
                    "dashboard_url": dashboard_url,
                    "subject": "Welcome to the ProAce Referral Program",
                },
            )
        return Response(
            MarketerSerializer(marketer).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="me")
    @extend_schema(responses=MarketerSerializer)
    def get_marketer(self, request: Request) -> Response:
        marketer = get_object_or_404(Marketer, user=request.user)
        return Response(MarketerSerializer(marketer).data)

    @action(detail=False, methods=["get"], url_path="wallet")
    @extend_schema(responses=AffiliateWalletSerializer)
    def wallet(self, request: Request) -> Response:
        wallet, _ = AffiliateWallet.objects.get_or_create(user=request.user)
        return Response(AffiliateWalletSerializer(wallet).data)

    @action(detail=False, methods=["get"], url_path="referrals")
    @extend_schema(
        parameters=[ListingQuerySerializer],
        responses=ReferralPageSerializer,
    )
    def referrals(self, request: Request) -> Response:
        marketer = get_object_or_404(Marketer, user=request.user)
        referrals = Referral.objects.filter(marketer=marketer)
        records = filter_records(
            referrals,
            request.query_params,
            search_fields=("id",),
            fields={"status": "status"},
        ).order_by("-created", "-pk")
        count, page = record_page(records, request.query_params)
        return Response({"count": count, "results": ReferralSerializer(page, many=True).data})

    @action(detail=False, methods=["post"], url_path="links")
    @extend_schema(request=AffiliateLinkRequestSerializer, responses=UrlSerializer)
    def create_link(self, request: Request) -> Response:
        marketer = get_object_or_404(Marketer, user=request.user)
        serializer = AffiliateLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=serializer.validated_data["product"])
        if (
            product.is_blocked
            or not product.visibility
            or product.store.status != "active"
            or not product.store.verified_at
        ):
            raise ValidationError({"product": "Choose an active, published product."})
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
        url_path=r"r/(?P<marketer_id>[^/.]+)/(?P<product_id>\d+)/(?P<identifier>[^/.]+)",
    )
    @transaction.atomic
    @extend_schema(
        parameters=[
            OpenApiParameter("marketer_id", OpenApiTypes.STR, OpenApiParameter.PATH),
            OpenApiParameter("product_id", OpenApiTypes.INT, OpenApiParameter.PATH),
            OpenApiParameter("identifier", OpenApiTypes.STR, OpenApiParameter.PATH),
        ],
        responses={302: None},
    )
    def redirect_url(
        self,
        request: Request,
        marketer_id: str | None = None,
        product_id: str | None = None,
        identifier: str | None = None,
    ) -> HttpResponse:
        url = get_object_or_404(
            Url.objects.select_for_update(),
            marketer__marketer_id=marketer_id,
            product_id=product_id,
            identifier=identifier,
            active=True,
            product__visibility=True,
            product__is_blocked=False,
            product__store__status="active",
            product__store__verified_at__isnull=False,
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
        url_path=r"clickbank/outbound/(?P<product_id>\d+)",
    )
    @extend_schema(
        parameters=[
            OpenApiParameter("product_id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
        responses={302: None},
    )
    def clickbank_outbound(self, request: Request, product_id: int | None = None) -> HttpResponse:
        from urllib.parse import urlencode, parse_qs, urlsplit, urlunsplit
        from nanoid import generate
        from affiliates.models import ClickBankOutboundClick

        product = get_object_or_404(
            Product, pk=product_id, visibility=True, is_blocked=False,
            store__status='active', store__verified_at__isnull=False,
        )
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

