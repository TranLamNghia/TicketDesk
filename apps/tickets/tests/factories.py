import factory
from apps.tickets.models import Category, Ticket, TicketHistory, Comment
from apps.users.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ["username"]

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    role = User.Role.REQUESTER

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "tranlamnghia")
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ["name"]

    name = factory.Sequence(lambda n: f"Category {n}")


class TicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ticket

    title = factory.Faker("sentence", nb_words=6, locale="vi_VN")
    description = factory.Faker("paragraph", locale="vi_VN")
    priority = Ticket.Priority.MEDIUM
    category = factory.SubFactory(CategoryFactory)
    created_by = factory.SubFactory(UserFactory)


class TicketHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TicketHistory

    ticket = factory.SubFactory(TicketFactory)
    status = TicketHistory.Status.NEW


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    ticket = factory.SubFactory(TicketFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence", locale="vi_VN")
