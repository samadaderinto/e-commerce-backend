from rest_framework.exceptions import ValidationError


def is_own_store(product, user):
    return bool(user and user.is_authenticated and product.store.user_id == user.pk)


def validate_purchase(product, user):
    if is_own_store(product, user):
        raise ValidationError({'detail': 'You cannot buy products from any store you own.'})
