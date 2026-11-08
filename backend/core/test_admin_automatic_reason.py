from django.test import SimpleTestCase
from .ai_admin import AIForm
from .package_admin import PackageForm
from .example_admin import ExampleCategoryForm
from .limit_admin import SiteLimitsForm
from .admin import AccountOptionsForm


class AutomaticAdminReasonTests(SimpleTestCase):
    def test_optional_reason_is_hidden_and_missing_value_has_audit_default(self):
        for form_class, name in [(AIForm,'reason'),(PackageForm,'reason'),(ExampleCategoryForm,'reason'),(SiteLimitsForm,'reason'),(AccountOptionsForm,'settings_reason')]:
            with self.subTest(form=form_class):
                field=form_class.base_fields[name]
                self.assertTrue(field.widget.is_hidden)
                self.assertFalse(field.required)
                self.assertGreaterEqual(len(field.clean(None)),3)
                self.assertEqual(field.clean('explicit reason'),'explicit reason')
