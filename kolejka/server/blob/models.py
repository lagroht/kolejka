# vim:ts=4:sts=4:sw=4:expandtab

import datetime
import os
import uuid

from django.conf import settings
from django.db import models
#from mptt.models import MPTTModel, TreeForeignKey

#class Category(MPTTModel):
#    name                  = models.CharField(max_length=64, unique=True, null=False, blank=False)
#    parent                = TreeForeignKey('self', null=True, related_name='children')
#    count_quota_hard_spec = models.CharField(max_length=16, null=False, blank=False)
#    count_quota_hard      = models.BigIntegerField(null=False)
#    count_quota_soft_spec = models.CharField(max_length=16, null=False, blank=False)
#    count_quota_soft      = models.BigIntegerField(null=False)
#    count                 = models.BigIntegerField(null=False, default=0)
#    size_quota_hard_spec  = models.CharField(max_length=16, null=False, blank=False)
#    size_quota_hard       = models.BigIntegerField(null=False)
#    size_quota_soft_spec  = models.CharField(max_length=16, null=False, blank=False)
#    size_quota_soft       = models.BigIntegerField(null=False)
#    size                  = models.BigIntegerField(null=False, default=0)

class Blob(models.Model):
    hash        = models.CharField(max_length=64, unique=True, null=False)
    active      = models.BooleanField(default=True, null=False)
    size        = models.BigIntegerField(null=False)
    time_create = models.DateTimeField(auto_now_add=True, null=False)
    time_access = models.DateTimeField(auto_now=True, null=False)

    @staticmethod
    def blob_temp_path():
        subdir = datetime.datetime.now().strftime('temp/%Y/%m/%d')
        dirname = os.path.join(settings.BLOB_STORE_PATH, subdir)
        os.makedirs(dirname, exist_ok=True)
        filename = uuid.uuid4().hex
        return os.path.join(dirname, filename)

    @staticmethod
    def blob_store_path(hash):
        subdir = 'blob/{}/{}/{}'.format(hash[0:2], hash[2:4], hash[4:6])
        dirname = os.path.join(settings.BLOB_STORE_PATH, subdir)
        os.makedirs(dirname, exist_ok=True)
        filename = hash[6:]
        return os.path.join(dirname, filename)

    @staticmethod
    def blob_inactive_path(hash):
        subdir = 'inactive/{}/{}/{}'.format(hash[0:2], hash[2:4], hash[4:6])
        dirname = os.path.join(settings.BLOB_STORE_PATH, subdir)
        os.makedirs(dirname, exist_ok=True)
        filename = hash[6:]
        return os.path.join(dirname, filename)

    @property
    def store_path(self):
        return Blob.blob_store_path(self.hash)

    @property
    def inactive_path(self):
        return Blob.blob_inactive_path(self.hash)

    def open(self):
        if os.path.exists(self.store_path):
            return open(self.store_path, "rb")
        if os.path.exists(self.inactive_path):
            return open(self.inactive_path, "rb")

    def deactivate(self):
        if self.reference_set.count() > 0:
            return
        self.active = False
        self.save()
        if os.path.exists(self.store_path) and not os.path.exists(self.inactive_path):
            os.rename(self.store_path, self.inactive_path)
        if os.path.exists(self.inactive_path) and os.path.exists(self.store_path):
            os.unlink(self.store_path)

    def activate(self):
        self.active = True
        self.save()
        if os.path.exists(self.inactive_path) and not os.path.exists(self.store_path):
            os.rename(self.inactive_path, self.store_path)
        if os.path.exists(self.store_path) and os.path.exists(self.inactive_path):
            os.unlink(self.inactive_path)

class Reference(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    blob        = models.ForeignKey('Blob', on_delete=models.PROTECT)
    key         = models.CharField(max_length=64, unique=True, null=False)
    time_create = models.DateTimeField(auto_now_add=True, null=False)
    time_access = models.DateTimeField(auto_now=True, null=False)
    permanent   = models.BooleanField(default=False, null=False)
    public      = models.BooleanField(default=False, null=False)

def reference_init(instance, **kwargs):
    if not instance.key:
        instance.key = uuid.uuid4().hex

models.signals.post_init.connect(reference_init, Reference)