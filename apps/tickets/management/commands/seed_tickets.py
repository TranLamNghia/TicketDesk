import random
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tickets.models import Category, Ticket, TicketHistory
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed realistic sample data for TicketDesk (Users, Categories, Tickets, Status History)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=15,
            help="Number of tickets to generate (default: 15)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing tickets and histories before seeding",
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        if clear:
            self.stdout.write(
                self.style.WARNING("Deleting existing tickets and histories...")
            )
            Ticket.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS("All existing tickets deleted successfully!")
            )

        self.stdout.write(
            self.style.NOTICE(f"Starting data seeding ({count} tickets)...")
        )

        # Initialize sample IT support categories
        category_names = [
            "Hardware & Equipment",
            "Software & Applications",
            "Network & Corporate VPN",
            "Access Permissions & Accounts",
            "Email & Office 365 Services",
        ]
        categories = []
        for name in category_names:
            cat, _ = Category.objects.get_or_create(name=name)
            categories.append(cat)

        # Initialize sample users (Requesters and IT Support agents)
        requesters = []
        for i in range(1, 4):
            user, created = User.objects.get_or_create(
                username=f"requester_{i}",
                defaults={
                    "email": f"requester_{i}@ticketdesk.local",
                    "role": User.Role.REQUESTER,
                },
            )
            if created:
                user.set_password("Password123!")
                user.save()
            requesters.append(user)

        it_supports = []
        for name in ["agent_john", "agent_sarah"]:
            user, created = User.objects.get_or_create(
                username=name,
                defaults={
                    "email": f"{name}@ticketdesk.local",
                    "role": User.Role.IT_SUPPORT,
                },
            )
            if created:
                user.set_password("Password123!")
                user.save()
            it_supports.append(user)

        # 15 realistic IT Helpdesk sample issues for testing & full-text search
        realistic_issues = [
            (
                "3rd Floor printer paper jam",
                "HP LaserJet on floor 3 is not picking up paper from Tray 2. Attention LED is blinking red.",
            ),
            (
                "Cannot connect to corporate OpenVPN",
                "Getting 'TLS handshake failed: Authentication Failed' error when attempting remote VPN connection.",
            ),
            (
                "Request Developer access to Backend GitLab repo",
                "New developer onboarded today. Requesting maintainer access to ticketdesk backend repository.",
            ),
            (
                "External monitor flickering constantly",
                "Secondary monitor connected via HDMI flickers black every 30 seconds after waking from sleep.",
            ),
            (
                "Outlook desktop client not syncing inbox",
                "Outlook is stuck in 'Disconnected' status and not receiving incoming messages since 8:00 AM.",
            ),
            (
                "Request admin privileges for Docker Desktop installation",
                "Need elevated administrator permissions to install Docker Desktop and WSL 2 for local development.",
            ),
            (
                "Mechanical keyboard numeric keypad unresponsive",
                "Numpad keys on external USB keyboard do not register any input even when NumLock is activated.",
            ),
            (
                "Reset password for internal HR Portal",
                "User account locked out after 3 consecutive invalid login attempts. Please send temporary reset link.",
            ),
            (
                "Wi-Fi connection drops intermittently on Meeting Room B",
                "Laptops lose 5GHz Wi-Fi signal during Zoom conferences in conference room B on 2nd floor.",
            ),
            (
                "Zoom client crashes on screen sharing",
                "Zoom immediately exits with fatal crash code 0xC0000005 when sharing primary 4K display.",
            ),
            (
                "Blue Screen of Death (BSOD) on system startup",
                "Workstation crashes with CRITICAL_PROCESS_DIED error during Windows boot sequence.",
            ),
            (
                "Request license activation for JetBrains PyCharm Pro",
                "Need IDE license key assigned for new backend developer starting this sprint.",
            ),
            (
                "MacBook battery draining unusually fast",
                "MacBook Pro M2 battery drops from 100% to 20% in less than 2 hours of light web development.",
            ),
            (
                "Unable to access internal file server NAS",
                "Getting network error 0x80070035 'The network path was not found' when mapping \\\\nas-storage.",
            ),
            (
                "Request guest Wi-Fi voucher for client visit",
                "Need temporary 24-hour guest Wi-Fi access voucher for visiting technical partner engineers.",
            ),
        ]

        # Generate tickets (First 15 are realistic, remaining are bulk benchmark items)
        tickets_with_status = []
        for i in range(count):
            if i < len(realistic_issues):
                title, desc = realistic_issues[i]
                title = f"{title} #{i + 1}"
            else:
                title = f"Incident #{i + 1}"
                desc = f"Sample ticket description #{i + 1}"

            # Determine status first according to business workflow
            status = random.choice(TicketHistory.Status.values)

            if status in (TicketHistory.Status.NEW, TicketHistory.Status.CANCELLED):
                assignee = None
            elif status in (TicketHistory.Status.REJECTED):
                assignee = random.choice(it_supports)
            else:
                assignee = random.choice(it_supports)

            ticket = Ticket(
                title=title,
                description=desc,
                priority=random.choice(Ticket.Priority.values),
                category=random.choice(categories),
                created_by=random.choice(requesters),
                assignee=assignee,
            )
            tickets_with_status.append((ticket, status))

        with transaction.atomic():
            tickets_to_create = [item[0] for item in tickets_with_status]
            # Bulk insert tickets for high performance
            created_tickets = Ticket.objects.bulk_create(
                tickets_to_create, batch_size=1000
            )

            # Create corresponding status history record matching each ticket's assigned state
            histories_to_create = [
                TicketHistory(
                    ticket=created_ticket,
                    status=status,
                )
                for created_ticket, (_, status) in zip(
                    created_tickets, tickets_with_status
                )
            ]
            TicketHistory.objects.bulk_create(histories_to_create, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {count} tickets and {len(histories_to_create)} status history records!"
            )
        )
