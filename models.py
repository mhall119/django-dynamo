from django.db import models
from django.utils.translation import ugettext_lazy as _
from dynamo import actions
from django.db import connections, router, transaction, models, DEFAULT_DB_ALIAS

# Create your models here.

DJANGO_FIELD_MAP = {
    'dynamiccharfield':             'django.db.models.CharField',
    'dynamictextfield':             'django.db.models.TextField',
    'dynamicbooleanfield':          'django.db.models.BooleanField',
    'dynamicintegerfield':          'django.db.models.IntegerField',
    'dynamicpositiveintegerfield':  'django.db.models.PositiveIntegerField',
    'dynamicdatefield':             'django.db.models.DateField',
    'dynamictimefield':             'django.db.models.TimeField',
    'dynamicdatetimefield':         'django.db.models.DatetimeField',
    'dynamicurlfield':              'django.db.models.UrlField',
    'dynamic_field':                'django.db.models._Field',
    'dynamicforeignkeyfield':       'django.db.models.ForeignKey',
    'dynamicmanytomanyfield':       'django.db.models.ManyToManyField',
    'dynamic_field':                'django.db.models._Field',
}

DJANGO_FIELD_CHOICES = [(key, value) for key, value in DJANGO_FIELD_MAP.items()]

class DynamicApp(models.Model):

    class Meta:
        verbose_name = _('Dynamic Application')
        
    name = models.CharField(verbose_name=_('Application Name'),
                            help_text=_('Internal name for this model'),
                            max_length=64, unique=True,
                            null=False, blank=False)

    verbose_name = models.CharField(verbose_name=_('Verbose Name'),
                            help_text=_('Display name for this application'),
                            max_length=128, null=False, blank=False)
    
class DynamicModel(models.Model):

    class Meta:
        verbose_name = _('Dynamic Model')
        unique_together = (('app', 'name'),)
        
    name = models.CharField(verbose_name=_('Model Name'),
                            help_text=_('Internal name for this model'),
                            max_length=64, null=False, blank=False)

    verbose_name = models.CharField(verbose_name=_('Verbose Name'),
                            help_text=_('Display name for this model'),
                            max_length=128, null=False, blank=False)

    app = models.ForeignKey(DynamicApp, related_name='models',
                            null=False, blank=False)
                            
    def to_model(self):
        attrs = {}
        class Meta:
            app_label = self.app.name
            verbose_name = self.verbose_name
        attrs['Meta'] = Meta
        attrs['__module__'] = 'dynamo.dynamic_apps.%s.models' % self.app.name
        for field in self.fields.all():
            attrs[field.name] = field.to_field()
        return type(str(self.name), (models.Model,), attrs)
        
    def create(self, using=None):
        using = using or router.db_for_write(self.__class__, instance=self)
        actions.create(self.to_model(), using)
        
class DynamicModelField(models.Model):

    class Meta:
        verbose_name = _('Dynamic Model Field')
        unique_together = (('model', 'name'),)
        
    
    name = models.CharField(verbose_name=_('Field Name'),
                            help_text=_('Internal name for this field'),
                            max_length=64, null=False, blank=False)

    verbose_name = models.CharField(verbose_name=_('Verbose Name'),
                            help_text=_('Display name for this field'),
                            max_length=128, null=False, blank=False)

    model = models.ForeignKey(DynamicModel, related_name='fields',
                            null=False, blank=False)

    field_type = models.CharField(verbose_name=_('Field Type'),
                            help_text=_('Field Data Type'),
                            choices=DJANGO_FIELD_CHOICES, 
                            max_length=128, null=False, blank=False)

    null = models.BooleanField(verbose_name=_('Null'),
                            help_text=_('Can this field contain null values?'),
                            default=True, null=False, blank=False)

    blank = models.BooleanField(verbose_name=_('Blank'),
                            help_text=_('Can this field contain empty values?'),
                            default=True, null=False, blank=False)

    unique = models.BooleanField(verbose_name=_('Unique'),
                            help_text=_('Restrict this field to unique values'),
                            default=False, null=False, blank=False)

    help_text = models.CharField(verbose_name=_('Help Text'),
                            help_text=_('Short description of the field\' purpose'),
                            max_length=256, null=True, blank=True)
                            
    def to_field(self):
        # return models.Field(attributes)
        return models.CharField(max_length=5, default='test')
        pass
