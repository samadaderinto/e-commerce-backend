
from django.contrib.auth.tokens import PasswordResetTokenGenerator




class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) + str(timestamp) + str(user.is_active)
        )


generate_token = TokenGenerator()

PAYMENT_STATUS_CHOICE = (
    ("pnd", "pending"),
    ("sfl", "successful"),
    ('fld', "failed")
)

CATEGORIES_CHOICE = (
    ("FSHN", "fishing"),
    ("SPRT", "sports"),
    ("ELCT", "electronics"),
    ("PHNS", "phones"),
    ("GMES", "games"),
    ("TBLT", "tablets"),
    ("OUWR", "outwear"),
    ("PETS", "pets"),
    ("TOYS", "toys"),
    ("CMPT", "computing"),
    ("LNGR", "lingerie"),
    ("BOOK", "books")
)

ORDER_STATUS_CHOICE = (
    ("CND", "cancelled"),
    ("RFD", "refunded"),
    ("DLV", "delivered"),
    ("SHP", "shipped"),
    ("PKU", "picked up"),
    ("PND", "pending"),
    ("CFD", "confirmed")
)

LABEL_CHOICE = (

    ("NEW", "new"),
    ("", "none"),
    ("BTS", "bestseller"),
    ("SDT", "sold out")
)

USPS_SERVICE_CHOICE = (
    ("express", "none"),
    ("priority", "new"),
    ("firstclass", "bestseller")
)

DELIVERY_METHOD_CHOICE = (
    ("pckup", "pick up"),
    ("hmdlvry", "home delivery")
)
