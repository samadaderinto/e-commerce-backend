from datetime import datetime
from product.models import Product
from payment.models import Coupon
from store.models import Schedule
from django_cron import CronJobBase, Schedule as CronShedule


class deactivate_coupon(CronJobBase):
    RUN_EVERY_MINS = 1  # every 2 hours

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self):

        coupons = Coupon.objects.all()
        current_time = datetime.now()
        for coupon in coupons:
            exp = coupon.valid_to
            if exp <= current_time:
                coupon.active = False
                coupon.save()


class set_product_visibility(CronJobBase):
    RUN_EVERY_MINS = 1  # every 2 hours

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self):
        print("s")
        schedules = Schedule.objects.all()
        current_time = datetime.now()
        for schedule in schedules:
            if schedule.make_visible_at >= current_time:
                product = Product.objects.get(
                    id=schedule.productId).visibility = True
                schedule.delete()
                product.save()


class update_product_label(CronJobBase):
    RUN_EVERY_MINS = 1
    # every 2 hours

    schedule = CronShedule(run_every_mins=RUN_EVERY_MINS)

    def do(self):

        current_time = datetime.now()
        products = Product.objects.all()
        for product in products:
            # if product label has been unboarded over a week change label
            if product.created:
                product.label = ""
                product.save()
            elif product.available <= 0:
                product.label = "sold out"
                product.save()

            # if product has been sold many times in a short period of range
            # elif product.bought:
            #     product.label = "bestseller"
            #     product.save()
