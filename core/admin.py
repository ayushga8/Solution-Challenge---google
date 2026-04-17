from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Dataset, AnalysisResult, FairnessMetric


# ============================================================
# Custom Admin Site Configuration
# ============================================================
admin.site.site_header = '🛡️ Unbiased AI Decision — Admin Panel'
admin.site.site_title = 'Unbiased AI Admin'
admin.site.index_title = 'Dashboard'


# ============================================================
# Custom User Admin with Promote/Demote Actions
# ============================================================
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'role', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'groups', 'date_joined']
    actions = ['make_owner', 'make_moderator', 'remove_role', 'activate_users', 'deactivate_users']

    @admin.display(description='Role')
    def role(self, obj):
        if obj.is_superuser:
            return '👑 Owner'
        elif obj.groups.filter(name='Moderators').exists():
            return '🛡️ Moderator'
        elif obj.is_staff:
            return '👔 Staff (No Group)'
        return '👤 Normal User'

    @admin.action(description='👑 Make selected users Owner (Superuser)')
    def make_owner(self, request, queryset):
        count = queryset.update(is_staff=True, is_superuser=True)
        self.message_user(request, f'{count} user(s) promoted to Owner.')

    @admin.action(description='🛡️ Make selected users Moderator (Staff)')
    def make_moderator(self, request, queryset):
        from django.contrib.auth.models import Group
        mod_group, created = Group.objects.get_or_create(name='Moderators')
        
        count = queryset.update(is_staff=True, is_superuser=False)
        for user in queryset:
            user.groups.add(mod_group)
            
        if created:
            self.message_user(request, f'Moderators group was created. Please assign permissions to it.', level='WARNING')
            
        self.message_user(request, f'{count} user(s) promoted to Moderator.')

    @admin.action(description='❌ Remove Admin/Mod roles from selected users')
    def remove_role(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)  # Can't demote yourself
        count = queryset.update(is_staff=False, is_superuser=False)
        from django.contrib.auth.models import Group
        try:
            mod_group = Group.objects.get(name='Moderators')
            for user in queryset:
                user.groups.remove(mod_group)
        except Group.DoesNotExist:
            pass
            
        self.message_user(request, f'{count} user(s) demoted to Normal User.')

    @admin.action(description='🟢 Activate selected users')
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) activated.')

    @admin.action(description='🔴 Deactivate selected users')
    def deactivate_users(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)  # Can't deactivate yourself
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) deactivated.')


class FairnessMetricInline(admin.TabularInline):
    """Show metrics inline within AnalysisResult."""
    model = FairnessMetric
    extra = 0
    readonly_fields = ['metric_type', 'protected_attribute', 'value', 'threshold', 'status']
    can_delete = False


class AnalysisResultInline(admin.StackedInline):
    """Show analysis inline within Dataset."""
    model = AnalysisResult
    extra = 0
    readonly_fields = ['overall_score', 'overall_severity', 'created_at']
    can_delete = True


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'row_count', 'column_count', 'uploaded_at', 'is_analyzed', 'get_score']
    list_filter = ['is_analyzed', 'uploaded_at', 'user']
    search_fields = ['name', 'user__username']
    readonly_fields = ['row_count', 'column_count', 'columns_json', 'protected_attributes_json', 'uploaded_at']
    list_per_page = 25
    date_hierarchy = 'uploaded_at'
    inlines = [AnalysisResultInline]

    fieldsets = (
        ('Dataset Info', {
            'fields': ('name', 'user', 'file', 'uploaded_at')
        }),
        ('Metadata', {
            'fields': ('row_count', 'column_count', 'target_column', 'is_analyzed'),
            'classes': ('collapse',),
        }),
        ('Raw Data (JSON)', {
            'fields': ('columns_json', 'protected_attributes_json'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Fairness Score')
    def get_score(self, obj):
        try:
            return f"{obj.analysis.overall_score:.1f}%"
        except AnalysisResult.DoesNotExist:
            return '—'


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'overall_severity', 'formatted_score', 'created_at', 'metric_count']
    list_filter = ['overall_severity', 'created_at']
    search_fields = ['dataset__name']
    readonly_fields = ['created_at']
    list_per_page = 25
    inlines = [FairnessMetricInline]

    fieldsets = (
        ('Analysis Overview', {
            'fields': ('dataset', 'overall_score', 'overall_severity', 'created_at', 'summary')
        }),
        ('Detailed Data (JSON)', {
            'fields': ('recommendations_json', 'detailed_results_json'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Score')
    def formatted_score(self, obj):
        severity_colors = {
            'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'
        }
        icon = severity_colors.get(obj.overall_severity, '')
        return f"{icon} {obj.overall_score:.1f}%"

    @admin.display(description='Metrics')
    def metric_count(self, obj):
        return obj.metrics.count()


@admin.register(FairnessMetric)
class FairnessMetricAdmin(admin.ModelAdmin):
    list_display = ['get_dataset', 'metric_type', 'protected_attribute', 'formatted_value', 'threshold', 'status_icon']
    list_filter = ['metric_type', 'status', 'protected_attribute']
    search_fields = ['analysis__dataset__name', 'protected_attribute']
    list_per_page = 50

    @admin.display(description='Dataset')
    def get_dataset(self, obj):
        return obj.analysis.dataset.name

    @admin.display(description='Value')
    def formatted_value(self, obj):
        return f"{obj.value:.4f}"

    @admin.display(description='Status')
    def status_icon(self, obj):
        icons = {'pass': '✅ Pass', 'warning': '⚠️ Warning', 'fail': '❌ Fail'}
        return icons.get(obj.status, obj.status)
