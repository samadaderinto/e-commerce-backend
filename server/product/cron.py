from datetime import timedelta
from django.utils import timezone
from product.models import Product
from payment.models import Coupon
from store.models import Schedule
from django_cron import CronJobBase, Schedule as CronShedule


class deactivate_coupon(CronJobBase):
    RUN_EVERY_MINS = 1  # every 2 hours

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self) -> None:

        coupons = Coupon.objects.all()
        current_time = timezone.now()
        for coupon in coupons:
            exp = coupon.valid_to
            if exp <= current_time:
                coupon.active = False
                coupon.save()


class set_product_visibility(CronJobBase):
    RUN_EVERY_MINS = 1  # every 2 hours

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self) -> None:
        from store.services import publish_due_products

        publish_due_products()


class update_product_label(CronJobBase):
    RUN_EVERY_MINS = 1
    # every 2 hourssawawa`1`

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self) -> None:

        current_time = timezone.now()
        products = Product.objects.all()
        for product in products:
            # if product label has been unboarded over a week change label
            if product.label == 'new' and product.created <= current_time - timedelta(days=7):
                product.label = ""
                product.save()
            elif product.product_type != 'affiliate_clickbank' and not product.is_digital and product.available <= 0:
                product.label = "sold out"
                product.save()

            # if product has been sold many times in a short period of range
            # elif product.bought:
            #     product.label = "bestseller"
            #     product.save()
