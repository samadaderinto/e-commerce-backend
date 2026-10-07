from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Set a privileged account password locally when email recovery is unavailable.'
    def add_arguments(self, parser):
        parser.add_argument('identifier', help='Privileged user email or username')
        parser.add_argument('--password', help='New password; omit to enter it securely')
        parser.add_argument('--deactivate-others', action='store_true', help='Deactivate other privileged accounts')
    def handle(self, *args, **opts):
        User = get_user_model()
        try: user = User.objects.get(email__iexact=opts['identifier'])
        except User.DoesNotExist:
            try: user = User.objects.get(username__iexact=opts['identifier'])
            except User.DoesNotExist: raise CommandError('Privileged user not found.')
        if not (user.is_superuser or user.is_staff or getattr(user, 'is_business_admin', False)):
            raise CommandError('Refusing to modify a non-privileged account.')
        password = opts['password'] or getpass('New password: ')
        confirm = opts['password'] or getpass('Confirm password: ')
        if len(password) < 12 or password != confirm: raise CommandError('Passwords must match and be at least 12 characters.')
        user.set_password(password)
        if hasattr(user, 'must_change_password'): user.must_change_password = True
        user.save(update_fields=['password'] + (['must_change_password'] if hasattr(user, 'must_change_password') else []))
        from core.auth_sync import sync_technical_admin_credentials, is_technical_super_admin
        if is_technical_super_admin(user):
            sync_res = sync_technical_admin_credentials(user, password)
            self.stdout.write(self.style.NOTICE(f'Technical admin external sync status: {sync_res}'))
        if opts['deactivate_others']:
            User.objects.filter(is_staff=True).exclude(pk=user.pk).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Recovery password set for {user.email or user.username}.'))
