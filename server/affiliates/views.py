from django.shortcuts import get_object_or_404, redirect
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from affiliates.models import AffiliateWallet, Marketer, Referral, Url
from affiliates.serializers import (
    AffiliateWalletSerializer,
    MarketerSerializer,
    ReferralSerializer,
    UrlSerializer,
)
from product.models import Product


class AffiliatesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "redirect_url":
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
        referrals = Referral.objects.filter(marketer=marketer).select_related("referred_user")
        return Response(ReferralSerializer(referrals, many=True).data)

    @action(detail=False, methods=["post"], url_path="links")
    def create_link(self, request):
        marketer = get_object_or_404(Marketer, user=request.user)
        product = get_object_or_404(Product, pk=request.data.get("product"))
        identifier = request.data.get("identifier") or f"product-{product.pk}"
        url, _ = Url.objects.get_or_create(
            marketer=marketer,
            product=product,
            identifier=identifier,
            defaults={"abs_url": ""},
        )
        url.abs_url = request.build_absolute_uri(
            f"/affiliate/r/{marketer.marketer_id}/{product.pk}/{identifier}/"
        )
        url.active = True
        url.save(update_fields=["abs_url", "active", "updated"])
        return Response(UrlSerializer(url).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"r/(?P<marketer_id>[^/.]+)/(?P<product_id>[^/.]+)/(?P<identifier>[^/.]+)",
    )
    def redirect_url(self, request, marketer_id=None, product_id=None, identifier=None):
        url = get_object_or_404(
            Url,
            marketer__marketer_id=marketer_id,
            product_id=product_id,
            identifier=identifier,
            active=True,
        )
        return redirect(f"/products/{url.product_id}/", permanent=False)
