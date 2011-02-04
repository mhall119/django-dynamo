from dynamo.models import DynamicApp, DynamicModel, DynamicModelField
from django.contrib import admin

def create_tables(modeladmin, request, queryset):
    for m in queryset.all():
        m.create()
create_tables.short_description = "Create tables for selected Models"

class DynamicAppAdmin(admin.ModelAdmin):
    fields = ('name', 'verbose_name')
    search_fields = ('name','verbose_name')
    ordering = ('name',)
    list_display = ('name', 'verbose_name')
admin.site.register(DynamicApp, DynamicAppAdmin)

class DynamicModelAdmin(admin.ModelAdmin):
    fields = ('name', 'app', 'verbose_name')
    search_fields = ('name','verbose_name')
    ordering = ('app','name')
    list_display = ('app', 'name', 'verbose_name')
    list_filter = ('app',)
    actions = [create_tables]
    
admin.site.register(DynamicModel, DynamicModelAdmin)

class DynamicModelFieldAdmin(admin.ModelAdmin):
    search_fields = ('name','verbose_name', 'field_type')
    ordering = ('name',)
    list_display = ('model', 'name', 'verbose_name')
    list_filter = ('model',)
admin.site.register(DynamicModelField, DynamicModelFieldAdmin)

for model in DynamicModel.objects.all():
    admin.site.register(model.as_model(), admin.ModelAdmin)
