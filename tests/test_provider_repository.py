from app.models.enums import ProviderRole
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository


def make_provider(**overrides):
    defaults = dict(name="Dr. Alex Rivera", role=ProviderRole.PSYCHIATRIC_CONSULTANT)
    defaults.update(overrides)
    return Provider(**defaults)


def test_create_and_get_by_id(db_session):
    repo = ProviderRepository(db_session)
    created = repo.create(make_provider())

    assert created.provider_id is not None
    fetched = repo.get_by_id(created.provider_id)
    assert fetched is not None
    assert fetched.name == "Dr. Alex Rivera"
    assert fetched.role == ProviderRole.PSYCHIATRIC_CONSULTANT


def test_phone_and_email_are_optional(db_session):
    repo = ProviderRepository(db_session)
    created = repo.create(make_provider(name="Jamie Lee", role=ProviderRole.CARE_MANAGER))

    assert created.phone is None
    assert created.email is None


def test_list_by_role_filters_correctly(db_session):
    repo = ProviderRepository(db_session)
    repo.create(make_provider(name="Care Manager One", role=ProviderRole.CARE_MANAGER))
    repo.create(make_provider(name="Care Manager Two", role=ProviderRole.CARE_MANAGER))
    repo.create(make_provider(name="Consultant One", role=ProviderRole.PSYCHIATRIC_CONSULTANT))

    care_managers = repo.list_by_role(ProviderRole.CARE_MANAGER)
    assert {p.name for p in care_managers} == {"Care Manager One", "Care Manager Two"}


def test_update_changes_fields(db_session):
    repo = ProviderRepository(db_session)
    provider = repo.create(make_provider(name="Sam Chen", role=ProviderRole.PRIMARY_CARE_PROVIDER))

    updated = repo.update(provider, phone="555-0100", email="sam.chen@example.com")

    assert updated.phone == "555-0100"
    assert updated.email == "sam.chen@example.com"
