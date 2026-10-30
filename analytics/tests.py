from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from main.models import WasteReport
from analytics.models import DashboardPreset

class DashboardTests(TestCase):
    def setUp(self):
        # Initialize a test client and create two test users
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        
        # Create  waste reports
        WasteReport.objects.create(
            reporter=self.user, 
            title='Test Food Waste', 
            status='RESOLVED', city='Jakarta Selatan', district='Tebet', 
            waste_type='FOOD', severity='HIGH',
            latitude=-6.2297, longitude=106.8166
        )

        WasteReport.objects.create(
            reporter=self.other_user, 
            title='Test Food Waste', 
            status='PENDING', city='Jakarta Selatan', district='Kebayoran', 
            waste_type='MIXED', severity='MEDIUM',
            latitude=-6.2425, longitude=106.8049
        )
        
        # Create a test preset that belongs to 'testuser'
        self.preset = DashboardPreset.objects.create(
            user=self.user,
            name='High Severity South Jakarta',
            city='Jakarta Selatan',
            severity='HIGH'
        )

    def test_dashboard_view_status_and_context(self):
        # Test whether the dashboard loads successfully and passes correct context
            
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('analytics:show_analytics'))
            
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/analytics_dashboard.html')
            
        # Check whether context variables exist
        self.assertIn('waste_reports', response.context)
        self.assertIn('presets', response.context)
            
        # Check whether the preset is loaded for the user
        self.assertEqual(len(response.context['presets']), 1)

    def test_dashboard_filtering_by_preset(self):
        #Test whether the dashboard applies the preset filters 
        
        self.client.login(username='testuser', password='password123')
        
        # Access the dashboard using the preset URL parameter
        response = self.client.get(reverse('analytics:show_analytics'), {'preset': self.preset.id})
        
        self.assertEqual(response.status_code, 200)
        
        # Check whether there's only 1 report matches 'Jakarta Selatan' AND 'HIGH' severity
        self.assertEqual(response.context['waste_reports'], 1)

    def test_save_preset_creates_database_record(self):
        # Test whether the save_preset view creates a new preset

        self.client.login(username='testuser', password='password123')
        
        form_data = {
            'name': 'Package Waste Filter',
            'city': 'Depok',
            'district': '',
            'waste_type': 'PACKAGING',
            'severity': 'LOW'
        }
        
        response = self.client.post(reverse('analytics:save_preset'), data=form_data)
        
        # Check whether that the view redirects back to the dashboard
        self.assertRedirects(response, reverse('analytics:show_analytics'))
        
        # Verify whether the preset was saved to the database
        preset_exists = DashboardPreset.objects.filter(name='Package Waste Filter', user=self.user).exists()
        self.assertTrue(preset_exists)

    def test_delete_preset_removes_record(self):
        # Test whether the delete_preset view removes the correct record
        self.client.login(username='testuser', password='password123')
        
        response = self.client.post(reverse('analytics:delete_preset', args=[self.preset.id]))
        
        self.assertRedirects(response, reverse('analytics:show_analytics'))
        self.assertFalse(DashboardPreset.objects.filter(id=self.preset.id).exists())

    def test_unauthorized_user_cannot_delete_other_presets(self):
        # Test whether a user cannot delete a preset belonging to someone else
        
        # Login as another user
        self.client.login(username='otheruser', password='password123')
        
        # Attempt to delete testuser's preset (Should return 404 from get_object_or_404)
        response = self.client.post(reverse('analytics:delete_preset', args=[self.preset.id]))
        
        self.assertEqual(response.status_code, 404)
        
        # Verify whether the preset still exists in the database
        self.assertTrue(DashboardPreset.objects.filter(id=self.preset.id).exists())



class InvalidPresetInputTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

    def test_non_numeric_preset_is_ignored(self):
        # A hand-edited ?preset=abc should show the unfiltered dashboard, not crash
        response = self.client.get(reverse('analytics:show_analytics'), {'preset': 'abc'})
        self.assertEqual(response.status_code, 200)

    def test_preset_without_name_is_not_saved(self):
        response = self.client.post(reverse('analytics:save_preset'), data={'name': '   ', 'city': 'Depok'})
        self.assertRedirects(response, reverse('analytics:show_analytics'))
        self.assertFalse(DashboardPreset.objects.exists())

    def test_preset_with_missing_name_field_is_not_saved(self):
        response = self.client.post(reverse('analytics:save_preset'), data={'city': 'Depok'})
        self.assertRedirects(response, reverse('analytics:show_analytics'))
        self.assertFalse(DashboardPreset.objects.exists())
