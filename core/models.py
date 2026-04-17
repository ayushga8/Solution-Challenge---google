import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Dataset(models.Model):
    """Represents an uploaded CSV dataset for bias analysis."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='datasets')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    columns_json = models.TextField(default='[]')  # JSON list of column names
    protected_attributes_json = models.TextField(default='[]')  # Auto-detected protected attrs
    target_column = models.CharField(max_length=255, blank=True, null=True)
    is_analyzed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.name} ({self.row_count} rows)"

    @property
    def columns(self):
        return json.loads(self.columns_json)

    @columns.setter
    def columns(self, value):
        self.columns_json = json.dumps(value)

    @property
    def protected_attributes(self):
        return json.loads(self.protected_attributes_json)

    @protected_attributes.setter
    def protected_attributes(self, value):
        self.protected_attributes_json = json.dumps(value)


class AnalysisResult(models.Model):
    """Stores the complete bias analysis result for a dataset."""
    SEVERITY_CHOICES = [
        ('low', 'Low Bias'),
        ('medium', 'Medium Bias'),
        ('high', 'High Bias'),
        ('critical', 'Critical Bias'),
    ]

    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name='analysis')
    created_at = models.DateTimeField(default=timezone.now)
    overall_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='low')
    overall_score = models.FloatField(default=0.0)  # 0-100 fairness score
    summary = models.TextField(blank=True)
    recommendations_json = models.TextField(default='[]')
    detailed_results_json = models.TextField(default='{}')  # Full analysis data

    def __str__(self):
        return f"Analysis for {self.dataset.name} — {self.overall_severity}"

    @property
    def recommendations(self):
        return json.loads(self.recommendations_json)

    @recommendations.setter
    def recommendations(self, value):
        self.recommendations_json = json.dumps(value)

    @property
    def detailed_results(self):
        return json.loads(self.detailed_results_json)

    @detailed_results.setter
    def detailed_results(self, value):
        self.detailed_results_json = json.dumps(value)


class FairnessMetric(models.Model):
    """Individual fairness metric computed for a specific protected attribute."""
    METRIC_TYPES = [
        ('demographic_parity', 'Demographic Parity'),
        ('disparate_impact', 'Disparate Impact'),
        ('statistical_parity', 'Statistical Parity Difference'),
        ('equal_opportunity', 'Equal Opportunity'),
        ('group_size_ratio', 'Group Size Ratio'),
    ]
    STATUS_CHOICES = [
        ('pass', 'Pass'),
        ('warning', 'Warning'),
        ('fail', 'Fail'),
    ]

    analysis = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, related_name='metrics')
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    protected_attribute = models.CharField(max_length=255)
    value = models.FloatField()
    threshold = models.FloatField(default=0.8)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pass')
    details_json = models.TextField(default='{}')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['protected_attribute', 'metric_type']

    def __str__(self):
        return f"{self.get_metric_type_display()} for {self.protected_attribute}: {self.value:.3f}"

    @property
    def details(self):
        return json.loads(self.details_json)

    @details.setter
    def details(self, value):
        self.details_json = json.dumps(value)
