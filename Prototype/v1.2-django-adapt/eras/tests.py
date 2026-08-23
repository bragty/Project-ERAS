from django.test import SimpleTestCase
from django.urls import reverse


class ErasPageTests(SimpleTestCase):
    def test_home_route_renders_frontpage(self):
        response = self.client.get(reverse("eras:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Patientenauswahl")
        self.assertContains(response, "patientSearch")
        self.assertTemplateUsed(response, "eras/pages/home.html")

    def test_checklist_route_renders_checklist_shell(self):
        response = self.client.get(reverse("eras:checklist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "items-t1")
        self.assertContains(response, "tab-btn")
        self.assertContains(response, "Zur Patienten")
        self.assertContains(response, "pathway-rail")
        self.assertTemplateUsed(response, "eras/pages/checklist.html")
