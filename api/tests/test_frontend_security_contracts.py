from pathlib import Path


def test_auth_form_never_falls_back_to_get_with_password_fields() -> None:
    source = (
        Path(__file__).parents[2] / "web" / "src" / "components" / "auth-page.tsx"
    ).read_text(encoding="utf-8")

    assert '<form method="post" onSubmit={submit}' in source
    assert 'name="password"' in source
