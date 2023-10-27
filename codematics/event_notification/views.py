from django.db.models.signals import post_save

from notifications.signals import notify
from core.models import User
# from core.utilities import airship,ua

from payment.models import Order, Payment

staffs = User.objects.filter(is_staff=True)

def created_order_nofication(actor, verb, **kwargs):
    notify.send(actor=actor,recipient=staffs, verb=verb, **kwargs)

def order_payment_nofication(sender, instance, created, **kwargs):
    notify.send(instance, verb="was saved")

def store_withdrawed_cash_nofication(sender, instance, created, **kwargs):
    notify.send(instance, verb="was saved")


def refund_requested_nofication(sender, instance, created, **kwargs):
    notify.send(instance, verb="was saved")

def staff_created_nofication(sender, instance, created, **kwargs):
    notify.send(instance, verb="was saved")
    
post_save.connect(created_order_nofication, sender=Order)    
post_save.connect(order_payment_nofication, sender=Payment)    
post_save.connect(store_withdrawed_cash_nofication, sender=Order)
post_save.connect(refund_requested_nofication, sender=Order)
post_save.connect(staff_created_nofication, sender=Order)

# def push_notificatons():
#     push = airship.create_push()
#     push.audience = ua.all_
#     push.notification = ua.notification(
#     ios=ua.ios(alert='Hello iOS'),
#     android=ua.android(alert='Hello Android'))
#     push.device_types = ua.device_types('ios', 'android')


# def push_notification_ios():
#     push = airship.create_push()
#     push.audience = ua.or_(ua.alias('adam'), ua.ios_channel('some_ios_channel'))
#     push.notification = ua.notification(alert='Hello')
#     push.device_types = ua.device_types('ios')
#     push.send()    

# def push_notification_andr():
#     push = airship.create_push()
#     push.audience = ua.or_(ua.alias('adam'), ua.android_channel('some_ios_channel'))
#     push.notification = ua.notification(alert='Hello')
#     push.device_types = ua.device_types('ios')
#     push.send()  
    
    
# notify.send(actor, recipient, verb, action_object, target, level, description, public, timestamp, **kwargs)
# actor: An object of any type. (Required) Note: Use sender instead of actor if you intend to use keyword arguments
# recipient: A Group or a User QuerySet or a list of User. (Required)
# verb: An string. (Required)
# action_object: An object of any type. (Optional)
# target: An object of any type. (Optional)
# level: One of Notification.LEVELS ('success', 'info', 'warning', 'error') (default=info). (Optional)
# description: An string. (Optional)
# public: An boolean (default=True). (Optional)
# timestamp: An tzinfo (default=timezone.now()). (Optional)