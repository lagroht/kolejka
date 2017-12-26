# vim:ts=4:sts=4:sw=4:expandtab

import datetime
import os
import uuid

from django.conf import settings
from django.db import models

from kolejka.common import KolejkaTask, KolejkaResult
from kolejka.server.blob.models import Reference

class Task(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key         = models.CharField(max_length=64, unique=True, null=False)
    description = models.TextField()
    time_create = models.DateTimeField(auto_now_add=True, null=False)
    files       = models.ManyToManyField(Reference)

    def task(self, task_path=None):
        task = KolejkaTask(task_path)
        task.load(self.description)
        return task

class Result(models.Model):
    task        = models.OneToOneField(Task, on_delete=models.CASCADE)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    description = models.TextField()
    time_create = models.DateTimeField(auto_now_add=True, null=False)
    files       = models.ManyToManyField(Reference)

    def result(self, result_path=None):
        result = KolejkaResult(result_path)
        result.load(self.description)
        return result

def task_init(instance, **kwargs):
    if not instance.key:
        instance.key = uuid.uuid4().hex

models.signals.post_init.connect(task_init, Task)
