from django.db import models
from django.utils.translation import ugettext_lazy as _
from dynamo import actions, utils
from django.db import connections, router, transaction, models, DEFAULT_DB_ALIAS
from django.db.models.loading import cache
from django.utils.datastructures import SortedDict
from django.contrib.contenttypes.models import ContentType

# Create your models here.

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
}

DJANGO_FIELD_CHOICES = [
    ('Basic Fields', [(key, value[1]) for key, value in DJANGO_FIELD_MAP.items()])
]
def get_field_choices():
    del DJANGO_FIELD_CHOICES[:]
    DJANGO_FIELD_CHOICES.append(
        ('Basic Fields', [(key, value[1]) for key, value in DJANGO_FIELD_MAP.items()])
    )
    curlabel = None
    curmodels = None
    try:
        for c in ContentType.objects.all().order_by('app_label'):
            if c.app_label != curlabel:
                if curlabel is not None:
                    DJANGO_FIELD_CHOICES.append((curlabel.capitalize(), curmodels))
                curlabel = c.app_label
                curmodels = []
            curmodels.append((c.model, c.name.capitalize()))
        DJANGO_FIELD_CHOICES.append((curlabel.capitalize(), curmodels))
    except:
        # ContentTypes aren't available yet, maybe pre-syncdb
        print "WARNING: ContentType is not availble"
        pass
        
    return DJANGO_FIELD_CHOICES
        
class DynamicApp(models.Model):

    class Meta:
        verbose_name = _('Dynamic Application')
        
    name = models.SlugField(verbose_name=_('Application Name'),
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
        
    name = models.SlugField(verbose_name=_('Model Name'),
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
        _update_dynamic_field_choices()
        self.uncache()
        
    def __unicode__(self):
        return self.verbose_name
        
class DynamicModelField(models.Model):

    class Meta:
        verbose_name = _('Dynamic Model Field')
        unique_together = (('model', 'name'),)
        ordering = ('id',)
        
    def __init__(self, *args, **kargs):
        super(DynamicModelField, self).__init__(*args, **kargs)
        
    name = models.SlugField(verbose_name=_('Field Name'),
                            help_text=_('Internal name for this field'),
                            max_length=64, null=False, blank=False)

    verbose_name = models.CharField(verbose_name=_('Verbose Name'),
                            help_text=_('Display name for this field'),
                            max_length=128, null=False, blank=False)

    model = models.ForeignKey(DynamicModel, related_name='fields',
                            null=False, blank=False)

    field_type = models.CharField(verbose_name=_('Field Type'),
                            help_text=_('Field Data Type'),
                            choices=get_field_choices(), 
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
        }

        if self.default is not None and self.default != '':
            attrs['default'] = self.default

        field_class = None
        if self.field_type in DJANGO_FIELD_MAP:
            module, klass = DJANGO_FIELD_MAP[self.field_type]
            field_class = utils.get_module_attr(module, klass, models.CharField)
            
        if field_class is None:
            try:
                ctype = ContentType.objects.get(model=self.field_type)
                print "Found ctype: %s (%s.%s)" % (ctype, ctype.app_label, ctype.model)
                field_class = models.ForeignKey
                model_def = DynamicModel.objects.get(name__iexact=ctype.model, app__name__iexact=ctype.app_label)
                model_klass = model_def.as_model()
                attrs['to'] = model_klass
                if attrs['to'] is None:
                    del attrs['to']
                    raise Exception('Could not get model class from %s' % ctype.model)
            except Exception, e:
                print "Failed to set foreign key: %s" % e
                field_class = None
            
        if field_class is None:
            print "No field class found for %s, using CharField as default" % self.field_type
            field_class = models.CharField
            
        if field_class is models.CharField:
            attrs['max_length'] = 64
            
        return field_class(**attrs)
    
    def delete(self, using=None):
        from south.db import db
        model_class = self.model.as_model()
        table = model_class._meta.db_table
        db.delete_column(table, self.name)

        super(DynamicModelField, self).delete(using)
        self.model.uncache()
        
    def save(self, force_insert=False, force_update=False, using=None):
        from south.db import db
        create = False
        if self.pk is None or not self.__class__.objects.filter(pk=self.pk).exists():
            create = True

        model_class = self.model.as_model()
        field = self.as_field()
        table = model_class._meta.db_table
        if create:
            db.add_column(table, self.name, field, keep_default=False)
        else:
            pass#db.alter_column(table, self.name, field)
        
        super(DynamicModelField, self).save(force_insert, force_update, using)
        self.model.uncache()
            
    def __unicode__(self):
        return self.verbose_name
        
def _update_dynamic_field_choices():
    print "Updating dynamic field choices..."
    DynamicModelField._meta.get_field_by_name('field_type')[0]._choices = get_field_choices()
