__author__ = 'Sebastian Hofstetter'

from django.db import models


class Result(models.Model):
    """ Holds results of webscraping executions """
    key = models.TextField(primary_key=True)
    task_key = models.ForeignKey("Task")

    def get_key(self, selectors):
        if all([result_value_dict[selector.name] for selector in self.key_selectors]):
            result_id = u" ".join([str(result_value_dict[selector.name]) for selector in self.key_selectors])  # Assemble Result_key from key selectors
            return self.name + result_id