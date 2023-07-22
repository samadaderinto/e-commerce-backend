from rest_framework.response import Response
from rest_framework import serializers

from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import smart_str, smart_bytes, force_str, DjangoUnicodeDecodeError
from django.urls import reverse



from core.models import User
from core.utilities import generate_token, send_mail



class VerifyUserSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)

    class Meta:
        fields = ["email"]

        def validate(self, attrs):

            email = attrs["data"].get('email', "")
            mode = attrs["data"].get('mode', "signup")

            if mode == "signup":
                user = User.objects.get(email=email)
                uidb64 = urlsafe_base64_encode(user.id)
                token = str(generate_token.make_token(user))
                current_domain = get_current_site(
                    request=attrs["data"].get('request')).domain
                relative_link = reverse('email-verify')
                absolute_url = f'https://{current_domain}\{relative_link}?token={token}'
                data = {"firstname": user.firstname,
                        "absolute_url": absolute_url}
                send_mail("onboarding-user", user.email, data=data)

            else:
                try:
                    user = User.objects.get(email=email)
                    uidb64 = urlsafe_base64_encode(user.id)
                    token = str(generate_token.make_token(user))
                    current_domain = get_current_site(
                        request=attrs["data"].get('request')).domain
                    relative_link = reverse('email-verify')
                    absolute_url = f'https://{current_domain}\{relative_link}?token={token}'
                    data = {"firstname": user.firstname,
                            "absolute_url": absolute_url}
                    send_mail("password-reset", user.email, data=data)
                except:
                    Response("Account does not exist", status=404)
