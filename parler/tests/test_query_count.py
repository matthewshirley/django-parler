import datetime as dt

from django.core.cache import cache
from django.utils import translation
from django.utils.timezone import now

from parler import appsettings
from parler.cache import get_translation_cache_key
from parler.cache import _cache_translation_needs_fallback

from .testapp.models import DateTimeModel, SimpleModel
from .utils import AppTestCase, override_parler_settings


class QueryCountTests(AppTestCase):
    """
    Test model construction
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.country_list = (
            "Mexico",
            "Monaco",
            "Morocco",
            "Netherlands",
            "Norway",
            "Poland",
            "Portugal",
            "Romania",
            "Russia",
            "South Africa",
        )

        for country in cls.country_list:
            SimpleModel.objects.create(_current_language=cls.conf_fallback, tr_title=country)

        DateTimeModel.objects.create(
            _current_language=cls.conf_fallback, tr_title=country, datetime=now()
        )

    # def setUp(self):
    #    cache.clear()

    def assertNumTranslatedQueries(self, num, qs, language_code=None):
        # Use default language if available.
        if language_code is None:
            language_code = self.conf_fallback

        # Easier to understand then a oneline lambda
        # Using str(), not unicode() to be python 3 compatible.
        def test_qs():
            for obj in qs:
                str(obj.tr_title)

        # Queryset is not set to a language, the individual models
        # will default to the currently active project language.
        with translation.override(language_code):
            self.assertNumQueries(num, test_qs)

    def test_uncached_queries(self):
        """
        Test that uncached queries work, albeit slowly.
        """
        with override_parler_settings(PARLER_ENABLE_CACHING=False):
            self.assertNumTranslatedQueries(1 + len(self.country_list), SimpleModel.objects.all())

    def test_iteration_with_non_qs_methods(self):
        """
        Test QuerySet methods that do not return QuerySets of models.
        """
        # We have at least one object created in setUpClass.
        obj = DateTimeModel.objects.all()[0]
        self.assertEqual(obj, DateTimeModel.objects.language(self.conf_fallback).all()[0])
        # Test iteration through QuerySet of non-model objects.
        self.assertIsInstance(
            DateTimeModel.objects.language(self.conf_fallback).dates("datetime", "day")[0], dt.date
        )

    def test_prefetch_queries(self):
        """
        Test that .prefetch_related() works
        """
        with override_parler_settings(PARLER_ENABLE_CACHING=False):
            self.assertNumTranslatedQueries(
                2, SimpleModel.objects.prefetch_related("translations")
            )

    def test_model_cache_queries(self):
        """
        Test that the ``_translations_cache`` works.
        """
        cache.clear()

        with override_parler_settings(PARLER_ENABLE_CACHING=False):
            qs = SimpleModel.objects.all()
            self.assertNumTranslatedQueries(1 + len(self.country_list), qs)
            self.assertNumTranslatedQueries(
                0, qs
            )  # All should be cached on the QuerySet and object now.

            qs = SimpleModel.objects.prefetch_related("translations")
            self.assertNumTranslatedQueries(2, qs)
            self.assertNumTranslatedQueries(
                0, qs
            )  # All should be cached on the QuerySet and object now.

    def test_get_translation_cache_key_empty_prefix(self):
        """
        Test that ``get_translation_cache_key`` creates correct cache key if prefix is empty.
        """
        with override_parler_settings(PARLER_CACHE_PREFIX=""):
            model = SimpleModel.objects.first()
            field = model.translations.first()
            key = get_translation_cache_key(field.__class__, 1, "en")
        self.assertEqual(key, "parler.testapp.SimpleModelTranslation.1.en")

    def test_get_translation_cache_key_with_prefix(self):
        """
        Test that ``get_translation_cache_key`` creates correct cache key if prefix is set.
        """
        with override_parler_settings(PARLER_CACHE_PREFIX="mysite"):
            model = SimpleModel.objects.first()
            field = model.translations.first()
            key = get_translation_cache_key(field.__class__, 1, "en")
        self.assertEqual(key, "mysite.parler.testapp.SimpleModelTranslation.1.en")

    def test_get_translation_not_in_cache(self):
        """
        The default "missing" behaviour was modified as we saw translations being cached as 
        missing when they didn't miss.
        """
        cache.clear()

        with override_parler_settings(PARLER_ENABLE_CACHING=True):
            model = SimpleModel.objects.first()
            _cache_translation_needs_fallback(model, model.get_current_language(), model._parler_meta.root.rel_name)
            str(model.tr_title)

