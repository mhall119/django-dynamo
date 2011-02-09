from django.db import models
from django.utils.translation import ugettext_lazy as _
from dynamo import actions, utils
from django.db import connections, router, transaction, models, DEFAULT_DB_ALIAS
from django.db.models.loading import cache
from django.utils.datastructures import SortedDict
from django.contrib.contenttypes.models import ContentType

# Create your models here.

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
    
    def __unicode__(self):
        return self.verbose_name
        
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
        
    def uncache(self):
        ''' 
        Removes the model this instance represents from Django's cache
        
        We need to remove the model from the cache whenever we change it
        otherwise it won't have the changes next time it's loaded
        '''
                
        cached_models = cache.app_models.get(self.app.name, SortedDict())
        if cached_models.has_key(self.name.lower()):
            del cached_models[self.name.lower()]

    def as_model(self):
        attrs = {}
        class Meta:
            app_label = self.app.name
            verbose_name = self.verbose_name
        attrs['Meta'] = Meta
        attrs['__module__'] = 'dynamo.dynamic_apps.%s.models' % self.app.name
        def uni(self):
            unival = []
            for f in self._meta.fields:
                if len(unival) < 3 and f.__class__ is models.CharField:
                    unival.append(getattr(self, f.name))
            if len(unival) > 0:
                return u' '.join(unival)
            else:
                return self.verbose_name
        attrs['__unicode__'] = uni
        for field in self.fields.all():
            attrs[field.name] = field.as_field()
        return type(str(self.name), (models.Model,), attrs)
        
    def save(self, force_insert=False, force_update=False, using=None):
        using = using or router.db_for_write(self.__class__, instance=self)
        create = False
        if self.pk is None or not self.__class__.objects.filter(pk=self.pk).exists():
            create = True
        super(DynamicModel, self).save(force_insert, force_update, using)
        if create:
            actions.create(self.as_model(), using)
        self.uncache()
        
    def __unicode__(self):
        return self.verbose_name
        
class DynamicModelField(models.Model):

    class Meta:
        verbose_name = _('Dynamic Model Field')
        unique_together = (('model', 'name'),)
        
    DJANGO_FIELD_MAP = {
        'dynamicbooleanfield':          ('django.db.models', 'BooleanField'),
        'dynamiccharfield':             ('django.db.models', 'CharField'),
        'dynamicdatefield':             ('django.db.models', 'DateField'),
        'dynamicdatetimefield':         ('django.db.models', 'DatetimeField'),
        'dynamicintegerfield':          ('django.db.models', 'IntegerField'),
        'dynamicpositiveintegerfield':  ('django.db.models', 'PositiveIntegerField'),
        'dynamictextfield':             ('django.db.models', 'TextField'),
        'dynamictimefield':             ('django.db.models', 'TimeField'),
        'dynamicurlfield':              ('django.db.models', 'UrlField'),
#            'dynamicforeignkeyfield':       ('django.db.models', 'ForeignKey'),
#            'dynamicmanytomanyfield':       ('django.db.models', 'ManyToManyField'),
#            'dynamic_field':                ('django.db.models', '_Field'),
    }

    DJANGO_FIELD_CHOICES = [
        ('Basic Fields', [(key, value[1]) for key, value in DJANGO_FIELD_MAP.items()])
    ]
    curlabel = None
    curmodels = None
    for c in ContentType.objects.all().order_by('app_label'):
        if c.app_label != curlabel:
            if curlabel is not None:
                DJANGO_FIELD_CHOICES.append((curlabel.capitalize(), curmodels))
            curlabel = c.app_label
            curmodels = []
        curmodels.append((c.model, c.name.capitalize()))
        
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

    default = models.CharField(verbose_name=_('Default value'),
                               help_text=_('Default value given to this field when none is provided'),
                               max_length=32, null=True, blank=True)
                               
    help_text = models.CharField(verbose_name=_('Help Text'),
                            help_text=_('Short description of the field\' purpose'),
                            max_length=256, null=True, blank=True)
                            
    def as_field(self):
        attrs = {
            'verbose_name': self.verbose_name,
            'null': self.null,
            'blank': self.blank,
            'unique': self.unique,
            'help_text': self.help_text,
            'default': self.default,
        }

        field_class = None
        if self.field_type in self.DJANGO_FIELD_MAP:
            module, klass = self.DJANGO_FIELD_MAP[self.field_type]
            field_class = utils.get_module_attr(module, klass, models.CharField)
            
        if field_class is None:
            try:
                ctype = ContentType.objects.get(model=self.field_type)
                field_class = models.ForeignKey
                attrs['to'] = ctype.model_class()
            except:
                field_class = None
            
        if field_class is None:
            field_class = models.CharField
            
        if field_class is models.CharField:
            attrs['max_length'] = 64
            
        return field_class(**attrs)
    
    def delete(self, using=None):
        super(DynamicModelField, self).delete(using)
        
    def save(self, force_insert=False, force_update=False, using=None):
        from south.db import db
        create = False
        if self.pk is None or not self.__class__.objects.filter(pk=self.pk).exists():
            create = True

        if create:
            model_class = self.model.as_model()
            field = self.as_field()
            table = model_class._meta.db_table
            db.add_column(table, self.name, field, keep_default=False)
        else:
            # what changed?
            pass        
        super(DynamicModelField, self).save(force_insert, force_update, using)
        self.model.uncache()
            
    def __unicode__(self):
        return self.verbose_name
        

